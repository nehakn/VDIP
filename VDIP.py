# -*- coding: utf-8 -*-
"""
/***************************************************************************
 VDIP
                                 A QGIS plugin
 It computes site-specific soil line using NIR-Red band spectral space. Further, it estimates vegetation and drought indices.

        begin                : 2022-05-17
        git sha              : $Format:%H$
        copyright            : (C) 2022 by Neha K Nawandar
        email                : nehanawandar@gmail.com
 ***************************************************************************/

/***************************************************************************
 *                                                                         *
 *   This program is free software; you can redistribute it and/or modify  *
 *   it under the terms of the GNU General Public License as published by  *
 *   the Free Software Foundation; either version 2 of the License, or     *
 *   (at your option) any later version.                                   *
 *                                                                         *
 ***************************************************************************/
"""
from cmath import log
from qgis.PyQt.QtCore import QSettings, QTranslator, QCoreApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

import os
# from pty import slave_open
from qgis.PyQt import uic
from qgis.PyQt import QtWidgets

from PyQt5 import QtCore,QtGui,QtWidgets
from PyQt5.QtWidgets import *
import gdal
import numpy as np
import time,datetime

# Initialize Qt resources from file resources.py
from .resources import *
# Import the code for the dialog
from .VDIP_dialog import VDIPDialog
import os.path


class VDIP:
    """QGIS Plugin Implementation."""

    def __init__(self, iface):
        """Constructor.

        :param iface: An interface instance that will be passed to this class
            which provides the hook by which you can manipulate the QGIS
            application at run time.
        :type iface: QgsInterface
        """
        # Save reference to the QGIS interface
        self.iface = iface
        # initialize plugin directory
        self.plugin_dir = os.path.dirname(__file__)
        # initialize locale
        locale = QSettings().value('locale/userLocale')[0:2]
        locale_path = os.path.join(
            self.plugin_dir,
            'i18n',
            'VDIP_{}.qm'.format(locale))

        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

        self.dlg=VDIPDialog()

        # Declare instance attributes
        self.actions = []
        self.menu = self.tr(u'&VDIP')

        self.toolbar = self.iface.addToolBar(u'VDIP')
        self.toolbar.setObjectName(u'VDIP')

        # Check if plugin was started the first time in current QGIS session
        # Must be set in initGui() to survive plugin reloads
        self.first_start = None

    # noinspection PyMethodMayBeStatic
    def tr(self, message):
        """Get the translation for a string using Qt translation API.

        We implement this ourselves since we do not inherit QObject.

        :param message: String for translation.
        :type message: str, QString

        :returns: Translated version of message.
        :rtype: QString
        """
        # noinspection PyTypeChecker,PyArgumentList,PyCallByClass
        return QCoreApplication.translate('VDIP', message)


    def add_action(
        self,
        icon_path,
        text,
        callback,
        enabled_flag=True,
        add_to_menu=True,
        add_to_toolbar=True,
        status_tip=None,
        whats_this=None,
        parent=None):
        """Add a toolbar icon to the toolbar.

        :param icon_path: Path to the icon for this action. Can be a resource
            path (e.g. ':/plugins/foo/bar.png') or a normal file system path.
        :type icon_path: str

        :param text: Text that should be shown in menu items for this action.
        :type text: str

        :param callback: Function to be called when the action is triggered.
        :type callback: function

        :param enabled_flag: A flag indicating if the action should be enabled
            by default. Defaults to True.
        :type enabled_flag: bool

        :param add_to_menu: Flag indicating whether the action should also
            be added to the menu. Defaults to True.
        :type add_to_menu: bool

        :param add_to_toolbar: Flag indicating whether the action should also
            be added to the toolbar. Defaults to True.
        :type add_to_toolbar: bool

        :param status_tip: Optional text to show in a popup when mouse pointer
            hovers over the action.
        :type status_tip: str

        :param parent: Parent widget for the new action. Defaults None.
        :type parent: QWidget

        :param whats_this: Optional text to show in the status bar when the
            mouse pointer hovers over the action.

        :returns: The action that was created. Note that the action is also
            added to self.actions list.
        :rtype: QAction
        """

        icon = QIcon(icon_path)
        action = QAction(icon, text, parent)
        action.triggered.connect(callback)
        action.setEnabled(enabled_flag)

        if status_tip is not None:
            action.setStatusTip(status_tip)

        if whats_this is not None:
            action.setWhatsThis(whats_this)

        if add_to_toolbar:
            # Adds plugin icon to Plugins toolbar
            self.iface.addToolBarIcon(action)

        if add_to_menu:
            self.iface.addPluginToMenu(
                self.menu,
                action)

        self.actions.append(action)

        self.ini_display()

        return action

    def initGui(self):
        """Create the menu entries and toolbar icons inside the QGIS GUI."""

        icon_path = ':/plugins/VDIP/icon.png'
        self.add_action(
            icon_path,
            text=self.tr(u'VDIP'),
            callback=self.run,
            parent=self.iface.mainWindow())

        # will be set False in run()
        # self.first_start = True

        self.dlg.pb_red_band.clicked.connect(self.pb_red_band_clicked)
        self.dlg.pb_nir_band.clicked.connect(self.pb_nir_band_clicked)
        self.dlg.pb_compute.clicked.connect(self.pb_compute_clicked)
        self.dlg.pb_close.clicked.connect(self.pb_close_clicked)


    # get red band from the local directory
    def pb_red_band_clicked(self):
        global r_dataset,r_array,r_cols,r_rows,r_geoTransform,r_projection
        red_band_filename=QFileDialog.getOpenFileName(self.dlg,'Open corrected Red band','', '*.tif;*tiff;*TIF;*TIFF')
        red_band_path=red_band_filename[0]    
        r_dataset=gdal.Open(red_band_path)   
        red_band=r_dataset.GetRasterBand(1)
        r_rows=r_dataset.RasterXSize
        r_cols=r_dataset.RasterYSize
        r_geoTransform=r_dataset.GetGeoTransform()
        r_projection=r_dataset.GetProjection()
        r_band= r_dataset.GetRasterBand(1)
        r_array=r_dataset.ReadAsArray() 

        # display the location from where red band is taken
        logger=self.dlg.tb_display
        l1='\nRed band location:'+(red_band_path)
        logger.append(l1)

    # get nir band from the local directory
    def pb_nir_band_clicked(self):
        global n_dataset,n_array,n_cols,n_rows,n_geoTransform,n_projection
        nir_band_filename=QFileDialog.getOpenFileName(self.dlg,'Open corrected NIR band','', '*.tif;*tiff;*TIF;*TIFF')
        nir_band_path=nir_band_filename[0]
        n_dataset=gdal.Open(nir_band_path)
        nir_band=n_dataset.GetRasterBand(1)
        n_cols=n_dataset.RasterXSize
        n_rows=n_dataset.RasterYSize
        n_geoTransform=n_dataset.GetGeoTransform()
        n_projection=n_dataset.GetProjection()     
        n_band=n_dataset.GetRasterBand(1)
        n_array=n_dataset.ReadAsArray() 

        # display the location from where nir band is taken
        logger=self.dlg.tb_display
        l1='\nNIR band location:'+(nir_band_path)
        logger.append(l1)

    # compute the chosen parameters out of ndvi, pdi, sm, msavi; if selected
    # check whether the local soil line is to be computed
    # check whether the red and nir bands are to be clipped using a shape file or not
    def pb_compute_clicked(self):
        global r_n_raster_output,n_array,r_array,r_rows,r_cols,r_geoTransform,r_projection
        global slope,intercept # for the local soil line
        global shape_input,r_dataset,n_dataset

        global shape_input,r_dataset,n_dataset,r_array,n_array,r_rows,r_cols,r_geoTransform,r_projection
        global r_n_raster_output

        # clip the bands
        if self.dlg.cb_clip_bands.isChecked():
            shape_input=QFileDialog.getOpenFileName(self.dlg,'Select the shape file (.shp file only)','', '*.shp')
            shape_input=shape_input[0]
            # display the location from where the shape file is chosen
            logger=self.dlg.tb_display
            l1='\nSelected shape file:'+shape_input
            logger.append(l1)

            # common path to save the clipped red and nir bands and the estimated outputs
            r_n_raster_output=str(QFileDialog.getExistingDirectory(self.dlg,"Select the output directory to save outputs"))
            # display the location from where the clipped red and nir bands are stored
            logger=self.dlg.tb_display
            l1='\nChosen directory to store the clipped red and nir bands:'+r_n_raster_output
            logger.append(l1)

            # save the clipped red band image
            r_raster_input=r_dataset
            r_raster_output=r_n_raster_output+'/red_clipped_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            logger=self.dlg.tb_display
            l1='\nThe clipped red file path is:'+r_raster_output
            logger.append(l1)
            gdal.Warp(r_raster_output,r_raster_input,cutlineDSName=shape_input,format='GTiff',cropToCutline=True)
            r_dataset=gdal.Open(r_raster_output)
            red_band=r_dataset.GetRasterBand(1)
            r_rows=r_dataset.RasterXSize
            r_cols=r_dataset.RasterYSize
            r_geoTransform=r_dataset.GetGeoTransform()
            r_projection=r_dataset.GetProjection()
            r_band= r_dataset.GetRasterBand(1)
            r_array=r_dataset.ReadAsArray()
            logger=self.dlg.tb_display
            logger.append('\nRed band converted in array form')

            # save the clipped nir band image
            n_raster_input=n_dataset
            n_raster_output=r_n_raster_output+'/nir_clipped_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            logger=self.dlg.tb_display
            l1='\nThe clipped nir file path is:'+n_raster_output
            logger.append(l1)
            gdal.Warp(n_raster_output,n_raster_input,cutlineDSName=shape_input,format='GTiff',cropToCutline=True)
            n_dataset=gdal.Open(n_raster_output)
            nir_band=n_dataset.GetRasterBand(1)
            n_cols=n_dataset.RasterXSize
            n_rows=n_dataset.RasterYSize
            n_geoTransform=n_dataset.GetGeoTransform()
            n_projection=n_dataset.GetProjection()     
            n_band=n_dataset.GetRasterBand(1)
            n_array=n_dataset.ReadAsArray()
            logger=self.dlg.tb_display
            logger.append('\nNIR band converted in array form')           

        # do not clip the bands
        # in this case there is no need to save the red and nir bands
        # sinply get the red and nir bands in form of 2d array (using gdal for it)
        else:
            # common path to save the clipped red and nir bands and the estimated outputs
            r_n_raster_output=str(QFileDialog.getExistingDirectory(self.dlg,"Select the output directory to save outputs"))
            logger=self.dlg.tb_display
            l1='\nDirectory selected to store the outputs:'+r_n_raster_output
            logger.append(l1)
            
            red_band=r_dataset.GetRasterBand(1)
            r_rows=r_dataset.RasterXSize
            r_cols=r_dataset.RasterYSize
            r_geoTransform=r_dataset.GetGeoTransform()
            r_projection=r_dataset.GetProjection()
            r_band=r_dataset.GetRasterBand(1)
            r_array=r_dataset.ReadAsArray()
            logger=self.dlg.tb_display
            logger.append('\nRed band  converted in array form')

            nir_band=n_dataset.GetRasterBand(1)
            n_cols=n_dataset.RasterXSize
            n_rows=n_dataset.RasterYSize
            n_geoTransform=n_dataset.GetGeoTransform()
            n_projection=n_dataset.GetProjection()     
            n_band=n_dataset.GetRasterBand(1)
            n_array=n_dataset.ReadAsArray()
            # print('NIR band array:',n_array)
            logger=self.dlg.tb_display
            logger.append('\nNIR band converted in array form')     

        
        # check if compute local soil line check box is ticked or not
        # global slope,intercept,r_array,n_array
        if self.dlg.cb_local_soil_line.isChecked():
            # extracting soil line from the chosen red and nir bands
            r_array_1d=r_array.flatten()
            n_array_1d=n_array.flatten()

            red_min=min(i for i in r_array_1d if i>0)
            nir_min=min(i for i in n_array_1d if i>0)
            red_max=max(i for i in r_array_1d if i>0)
            nir_max=max(i for i in n_array_1d if i>0)
            # print('Red band surface reflectance minimum value:',red_min,', maximum value:',red_max)
            # print('NIR band surface reflectance minimum value:',nir_min,', maximum value:',nir_max)
            min_pos=np.where(r_array_1d==red_min)
            max_pos=np.where(r_array_1d==red_max)
            # print('Minumum value location:',min_pos,'Maximum value location:',max_pos)

            rho_red_min=red_min
            if nir_min<=n_array_1d[min_pos]:
                rho_nir_min=nir_min
            else:
                rho_nir_min=n_array_1d[min_pos]
        
            rho_red_max=red_max
            if nir_max==n_array_1d[max_pos]:
                rho_nir_max=nir_max
            else:
                rho_nir_max=n_array_1d[max_pos]

            # global slope
            slope1=(rho_nir_max-rho_nir_min)/(rho_red_max-rho_red_min)
            intercept1=-slope1*rho_red_min+rho_nir_min
            slope=slope1[0]
            intercept=intercept1[0]
            logger=self.dlg.tb_display
            l1='\nSoil line slope is '+str(slope)+' and, intercept is '+str(intercept)
            logger.append(l1)
        else:
            slope=1.0573
            intercept=0.0268
            logger=self.dlg.tb_display
            l1='\nSoil line slope is '+str(slope)+' and, intercept is '+str(intercept)
            logger.append(l1)

        sl_param=[slope,intercept]
        # saving the slope and intercept in a text file
        # sl_filename=str(QFileDialog.getExistingDirectory(self,"Select the output directory to save soil line information"))
        # sl_filename=r_n_raster_output
        # sl_filename=sl_filename+'/soil_line_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.txt'
        # np.savetxt(sl_filename,sl_param)

        # computing rvi
        if self.dlg.cb_rvi.isChecked():
            global rvi
            rvi=np.where(r_array==0.,0,n_array/r_array)
            driver=gdal.GetDriverByName("GTiff")
            if self.dlg.cb_clip_bands.isChecked():
                rvi_output_path=r_n_raster_output+'/rvi_clipped_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            else:
                rvi_output_path=r_n_raster_output+'/rvi_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            rvi_outData=driver.Create(rvi_output_path,r_rows,r_cols,1,gdal.GDT_Float64)
            rvi_outData.SetGeoTransform(r_geoTransform)
            rvi_outData.SetProjection(r_projection)
            rvi_outData.GetRasterBand(1).WriteArray(rvi)
            rvi_outData.FlushCache()
            logger=self.dlg.tb_display
            logger.append('\nRVI computed and tiff file is saved')


        # slope based vi (rvi, ndvi, ipvi, tvi)
        # check the check boxes, for, which parameters are to be computed
        # check if ndvi push button is clicked or not
        # compute ndvi if clicked and save the geotiff file
        if self.dlg.cb_ndvi.isChecked():
            global ndvi
            ndvi=np.where((n_array+r_array)==0.,0,(n_array-r_array)/(n_array+r_array))
            driver=gdal.GetDriverByName("GTiff")
            if self.dlg.cb_clip_bands.isChecked():
                ndvi_output_path=r_n_raster_output+'/ndvi_clipped_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            else:
                ndvi_output_path=r_n_raster_output+'/ndvi_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            ndvi_outData=driver.Create(ndvi_output_path,r_rows,r_cols,1,gdal.GDT_Float64)
            ndvi_outData.SetGeoTransform(r_geoTransform)
            ndvi_outData.SetProjection(r_projection)
            ndvi_outData.GetRasterBand(1).WriteArray(ndvi)
            ndvi_outData.FlushCache()
            logger=self.dlg.tb_display
            logger.append('NDVI computed and tiff file is saved')


        # computing ipvi
        if self.dlg.cb_ipvi.isChecked():
            global ipvi
            ipvi=np.where(r_array+n_array==0.,0,n_array/(r_array+n_array))
            driver=gdal.GetDriverByName("GTiff")
            if self.dlg.cb_clip_bands.isChecked():
                ipvi_output_path=r_n_raster_output+'/ipvi_clipped_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            else:
                ipvi_output_path=r_n_raster_output+'/ipvi_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            ipvi_outData=driver.Create(ipvi_output_path,r_rows,r_cols,1,gdal.GDT_Float64)
            ipvi_outData.SetGeoTransform(r_geoTransform)
            ipvi_outData.SetProjection(r_projection)
            ipvi_outData.GetRasterBand(1).WriteArray(ipvi)
            ipvi_outData.FlushCache()
            logger=self.dlg.tb_display
            logger.append('IPVI computed and tiff file is saved')

        # computing tvi
        if self.dlg.cb_tvi.isChecked():
            global tvi
            tvi=ndvi+0.5
            driver=gdal.GetDriverByName("GTiff")
            if self.dlg.cb_clip_bands.isChecked():
                tvi_output_path=r_n_raster_output+'/tvi_clipped_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            else:
                tvi_output_path=r_n_raster_output+'/tvi_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            tvi_outData=driver.Create(tvi_output_path,r_rows,r_cols,1,gdal.GDT_Float64)
            tvi_outData.SetGeoTransform(r_geoTransform)
            tvi_outData.SetProjection(r_projection)
            tvi_outData.GetRasterBand(1).WriteArray(tvi)
            tvi_outData.FlushCache()
            logger=self.dlg.tb_display
            logger.append('TVI computed and tiff file is saved')
        

        # distance based VI (pvi, dvi and tsavi)
        # check the pvi parameter box
        if self.dlg.cb_pvi.isChecked():
            pvi=np.abs((n_array-slope*r_array+intercept)/(np.sqrt(1+slope**2)))
            logger=self.dlg.tb_display
            driver=gdal.GetDriverByName("GTiff")
            if self.dlg.cb_clip_bands.isChecked():
                pvi_output_path=r_n_raster_output+'/pvi_clipped_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            else:
                pvi_output_path=r_n_raster_output+'/pvi_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            pvi_outData=driver.Create(pvi_output_path,r_rows,r_cols,1,gdal.GDT_Float64)
            pvi_outData.SetGeoTransform(r_geoTransform)
            pvi_outData.SetProjection(r_projection)
            pvi_outData.GetRasterBand(1).WriteArray(pvi)
            pvi_outData.FlushCache()
            logger=self.dlg.tb_display
            logger.append('PVI computed and tiff file is saved')

        # check the dvi parameter
        if self.dlg.cb_dvi.isChecked():
            dvi=slope*n_array+n_array
            logger=self.dlg.tb_display
            driver=gdal.GetDriverByName("GTiff")
            if self.dlg.cb_clip_bands.isChecked():
                dvi_output_path=r_n_raster_output+'/dvi_clipped_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            else:
                dvi_output_path=r_n_raster_output+'/dvi_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            dvi_outData=driver.Create(dvi_output_path,r_rows,r_cols,1,gdal.GDT_Float64)
            dvi_outData.SetGeoTransform(r_geoTransform)
            dvi_outData.SetProjection(r_projection)
            dvi_outData.GetRasterBand(1).WriteArray(dvi)
            dvi_outData.FlushCache()
            logger=self.dlg.tb_display
            logger.append('PVI computed and tiff file is saved')

        # check the tsavi parameter box
        if self.dlg.cb_tsavi.isChecked():
            global tsavi
            tsavi=(slope*(n_array-slope*r_array-intercept))/(r_array+slope*n_array-slope*intercept)
            logger=self.dlg.tb_display
            driver=gdal.GetDriverByName("GTiff")
            if self.dlg.cb_clip_bands.isChecked():
                tsavi_output_path=r_n_raster_output+'/tsavi_clipped_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            else:
                tsavi_output_path=r_n_raster_output+'/tsavi_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            tsavi_outData=driver.Create(tsavi_output_path,r_rows,r_cols,1,gdal.GDT_Float64)
            tsavi_outData.SetGeoTransform(r_geoTransform)
            tsavi_outData.SetProjection(r_projection)
            tsavi_outData.GetRasterBand(1).WriteArray(tsavi)
            tsavi_outData.FlushCache()
            logger=self.dlg.tb_display
            logger.append('TSAVI computed and tiff file is saved')


        # drought and soil moisture index parameters (pdi and sm)
        # check if pdi push button is clicked or not
        # compute pdi if clicked and save the geotiff file
        if self.dlg.cb_pdi.isChecked():
            global pdi
            m=slope
            pdi=(r_array+m*n_array)/(np.sqrt(1+m*m))
            driver=gdal.GetDriverByName("GTiff")
            if self.dlg.cb_clip_bands.isChecked():
                pdi_output_path=r_n_raster_output+'/pdi_clipped_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            else:
                pdi_output_path=r_n_raster_output+'/pdi_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            pdi_outData=driver.Create(pdi_output_path,r_rows,r_cols,1,gdal.GDT_Float64)
            pdi_outData.SetGeoTransform(r_geoTransform)
            pdi_outData.SetProjection(r_projection)
            pdi_outData.GetRasterBand(1).WriteArray(pdi)
            pdi_outData.FlushCache()
            logger=self.dlg.tb_display
            logger.append('PDI computed and tiff file is saved')
        
        # check if sm push button is clicked or not
        # compute sm if clicked and save the geotiff file
        if self.dlg.cb_sm.isChecked():
            global sm
            sm=1-pdi
            driver=gdal.GetDriverByName("GTiff")
            if self.dlg.cb_clip_bands.isChecked():
                sm_output_path=r_n_raster_output+'/sm_clipped_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            else:
                sm_output_path=r_n_raster_output+'/sm_%s' % (time.strftime("%d%m%Y_") + time.strftime("%H%M%S"))+'.tif'
            sm_outData=driver.Create(sm_output_path,r_rows,r_cols,1,gdal.GDT_Float64)
            sm_outData.SetGeoTransform(r_geoTransform)
            sm_outData.SetProjection(r_projection)
            sm_outData.GetRasterBand(1).WriteArray(sm)
            sm_outData.FlushCache()
            logger=self.dlg.tb_display
            logger.append('SM computed and tiff file is saved')
        
        # if no parameter is checked then no computation is required
        else:
            logger=self.dlg.tb_display
            logger.append('\nGo again')

    # to make sure that all the check boxes are unchecked on closing the plugin 
    # added on 15/05/2022
    def pb_close_clicked(self):
        global r_n_raster_output
        self.dlg.cb_clip_bands.setChecked(False)
        self.dlg.cb_local_soil_line.setChecked(False)

        self.dlg.cb_rvi.setChecked(False)
        self.dlg.cb_ndvi.setChecked(False)
        self.dlg.cb_ipvi.setChecked(False)
        self.dlg.cb_tvi.setChecked(False)

        self.dlg.cb_pvi.setChecked(False)
        self.dlg.cb_dvi.setChecked(False)
        self.dlg.cb_tsavi.setChecked(False)

        self.dlg.cb_pdi.setChecked(False)
        self.dlg.cb_sm.setChecked(False)
        self.dlg.close()


    def unload(self):
        """Removes the plugin menu item and icon from QGIS GUI."""
        for action in self.actions:
            self.iface.removePluginMenu(
                self.tr(u'&VDIP'),
                action)
            self.iface.removeToolBarIcon(action)


    def run(self):
        """Run method that performs all the real work"""

        # Create the dialog with elements (after translation) and keep reference
        # Only create GUI ONCE in callback, so that it will only load when the plugin is started
        if self.first_start == True:
            self.first_start = False
            self.dlg = VDIPDialog()

        # show the dialog
        self.dlg.show()

        self.dlg.setFixedSize(self.dlg.size())

        # Run the dialog event loop
        result = self.dlg.exec_()
        # See if OK was pressed
        if result:
            # Do something useful here - delete the line containing pass and
            # substitute with your code.
            pass


    def ini_display(self):
        # For terminal outputs
        # tb_display is name of the text display browser
        logger = self.dlg.tb_display
        logger.append(
            'VDIP: Vegetation and Drought Indices Parameter computation Plugin\n'
            '\nThis plugin computes the mentioned parameters, based on the selections made by the user. Follow the below given steps to use the plugin:'
            '\n-Select the corrected Red and NIR bands.'
            '\n-If bands need to be clipped, select the proper shape file.'
            '\n-If local soil line needs to be extracted, select the check box; else default values will be considered'
            '\n-Select the checkboxes for the parameters to be computed'
            '\n-Choose the output directory where all the clipped bands/ parameters will be saved'
            '\nNOTE: The PDI and SM parameters are meant to be computed for bare soil surfaces only.'
            '\n\n***********************************************************'
            '\nOutputs based on the selections made by the user:'
        )
