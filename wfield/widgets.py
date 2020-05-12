from .utils import *
from .allen import (load_allen_landmarks,
                    save_allen_landmarks,
                    allen_landmarks_to_image_space,
                    allen_transform_from_landmarks,
                    allen_load_reference,
                    allen_transform_regions)

from PyQt5.QtWidgets import (QApplication,
                             QWidget,
                             QTableWidgetItem,
                             QDockWidget,
                             QFormLayout,
                             QHBoxLayout,
                             QVBoxLayout,
                             QGridLayout,
                             QMainWindow,
                             QGroupBox,
                             QSlider,
                             QWidgetAction,
                             QListWidget,
                             QComboBox,
                             QPushButton,
                             QLabel,
                             QLineEdit,
                             QTextEdit,
                             QDoubleSpinBox,
                             QSpinBox,
                             QCheckBox,
                             QProgressBar,
                             QFileDialog,
                             QAction)

from PyQt5 import QtCore
from PyQt5.QtCore import Qt,QTimer

import pyqtgraph as pg
pg.setConfigOption('crashWarning', False)
pg.setConfigOption('background', 'w')
pg.setConfigOption('foreground', 'k')
pg.setConfigOptions(imageAxisOrder='row-major')
axiscolor = 'k'

class AllenMatchTable(QWidget):
    def __init__(self, landmarks_file = None,parent = None):
        super(AllenMatchTable,self).__init__()
        # This widget shows: bregmaoffset in image coordinates, resolution, landmarks table
        lmarks = load_allen_landmarks(landmarks_file)
        self.landmarks_file = landmarks_file
        self.parent  = parent
        if ('landmarks' in lmarks.keys() and 
            'bregma_offset' in lmarks.keys() and
            'resolution' in lmarks.keys()):
            landmarks_im = allen_landmarks_to_image_space(
                lmarks['landmarks'].copy(), 
                lmarks['bregma_offset'],
                lmarks['resolution'])
            x = landmarks_im['x']
            y = landmarks_im['y']
            if 'landmarks_match' in lmarks.keys():
                x = lmarks['landmarks_match']['x']
                y = lmarks['landmarks_match']['y']
            landmarks_im['nx'] = x
            landmarks_im['ny'] = y
        else:
            print('Need (landmarks,bregma_offset,resolution) in the landmarks file.')
            return
        self.table = pg.TableWidget()
        self.landmarks_im = landmarks_im
        self.landmarks = lmarks['landmarks']
        self.resolution = lmarks['resolution']
        self.bregma_offset = lmarks['bregma_offset']
        if 'transform' in lmarks.keys():
            self.M = lmarks['transform']
            self.parent.M = self.M
        self.table.setData(landmarks_im.to_records(index = False))
        lay = QFormLayout()
        self.setLayout(lay)

        w = QWidget()
        l = QFormLayout()
        w.setLayout(l)
        # resolution
        self.wres = QLineEdit()
        self.wres.setText(str(self.resolution))
        l.addRow(QLabel('resolution  [mm/pixel]'),self.wres)
        # bregma offset
        self.wbregma = QLineEdit()
        self.wbregma.setText('{0},{1}'.format(*self.bregma_offset))
        l.addRow(QLabel('bregma_offset'),self.wbregma)

        def ubregma():
            tt = self.wbregma.text()
            try:
                tt = tt.split(',')
                self.bregma_offset = [int(tt[0]),int(tt[1])]
            except Exception as e:
                print(e)
                print('bregma_offset: Needs 2 comma separated values.')
        self.wbregma.textChanged.connect(ubregma)

        def ures():
            tt = self.wres.text()
            try:
                self.resolution = float(tt)
            except Exception as e:
                print(e)
                print('Resolution needs to be a float.')
        self.wbregma.textChanged.connect(ubregma)
        # save transform
        self.wsave = QPushButton('Save points')
        l.addRow(self.wsave)
        
        def usave():
            if self.parent.folder is None:
                print('Folder is not defined..')
            if landmarks_file is None: # then it is the dorsal_cortex
                fname = 'dorsal_cortex_landmarks.json'
            else:
                fname = os.path.basename(landmarks_file)
            fname = pjoin(self.parent.folder, fname)
            landmarks_match = self.landmarks.copy()
            landmarks_match.x = self.landmarks_im.nx
            landmarks_match.y = self.landmarks_im.ny
            landmarks_im = allen_landmarks_to_image_space(
                self.landmarks.copy(), 
                self.bregma_offset,
                self.resolution)
            self.M = allen_transform_from_landmarks(landmarks_im,landmarks_match)
            save_allen_landmarks(self.landmarks,filename = fname,
                                 resolution = self.resolution,
                                 bregma_offset = self.bregma_offset,
                                 landmarks_match = landmarks_match,
                                 transform = self.M)
            self.parent.M = self.M
        self.wsave.clicked.connect(usave)    
        lay.addRow(self.table,w)
        
class ImageWidget(QWidget):
    def __init__(self):
        super(ImageWidget,self).__init__()

        self.layout = QFormLayout()
        self.setLayout(self.layout)
        self.win = pg.GraphicsLayoutWidget()
        self.pl = self.win.addPlot()
        self.pl.getViewBox().invertY(True)
        self.pl.getViewBox().setAspectLocked(True)
        
        self.im = pg.ImageItem()
        self.win.setCentralWidget(self.pl)
        self.pl.addItem(self.im)
        
        self.pl.getAxis('bottom').setPen(axiscolor)
        self.pl.getAxis('left').setPen(axiscolor)
        self.layout.addRow(self.win)

    def _add_hist(self):
        self.hist = pg.HistogramLUTItem()
        self.hist.setImageItem(self.im)
        self.pl.addItem(self.hist)

class QAllenAreasPlot():
    def __init__(self,plot,
                 reference='dorsal_cortex',
                 parent = None,
                 resolution = 0.01,
                 bregma_offset = [0,0]):
        self.ccf_regions,self.proj,self.brain_outline = allen_load_reference(reference)
        self.parent = parent
        self.landmarks = None
        self.resolution = resolution
        self.sides = ['left','right']
        if hasattr(self.parent.parent,'allenparwidget'):
            self.landmarks = self.parent.parent.allenparwidget.landmarks
            self.resolution = self.parent.parent.allenparwidget.resolution
            self.bregma_offset = self.parent.parent.allenparwidget.bregma_offset
            self.M = self.parent.parent.allenparwidget.M
        self.plot = plot
        self.plot_items = []
        self.plot_text = []
        self.plot_centers = []
        self.warped_image = self.parent.warp_im # then transform the points'

    def update(self):
        self.warped_image = self.parent.warp_im # then transform the points'
        if self.warped_image:
            M = None
        else:
            M = self.M
        nccf_regions = allen_transform_regions(M, self.ccf_regions,
                                               resolution = self.resolution,
                                               bregma_offset = self.bregma_offset)
        self.remove()
        for iarea,area in nccf_regions.iterrows():
            for side in self.sides:
                self.plot_items.append(pg.PlotCurveItem())
                self.plot_items[-1].setData(x = area[side+'_x'],y = area[side+'_y'])
                self.plot_text.append(area['acronym'])
                self.plot_centers.append(area[side+'_center'])
                self.plot.addItem(self.plot_items[-1])
    def remove(self):
        for p in self.plot_items:
            p.setVisible(False)
            p.scene().removeItem(p)
        self.plot_items = []
        self.plot_text = []
        self.plot_centers = []

            
class CustomDragPoints(pg.GraphItem):
    def __init__(self):
        self.drag_points = None
        self.drag_offset = None
        self.text = []
        self.text_items = []
        pg.GraphItem.__init__(self)

    def setData(self, points = None, text = None):
        # pass a list of dictionaries (with pos and text as keys)
        if points is None:
            return
        if text is None:
            text = self.text
        else:
            self.text = text
        self.points = points
        self.scatter.setData(self.points)
        for i in self.text_items:
            i.scene().removeItem(i)
        self.text_items = []
        for p,t in zip(self.points,text):
            self.text_items.append(pg.TextItem(text=t,color='y'))
            self.text_items[-1].setParentItem(self)
            self.text_items[-1].setPos(*p['pos'])
        self.informViewBoundsChanged()
    def set_visible(self,val):
        self.scatter.setVisible(val)
        for t in self.text_items:
            t.setVisible(val)
            
    def _findind(self,pt):
        for i,p in enumerate(self.points):
            if ((pt.pos().x() == p['pos'][0]) and
                (pt.pos().y() == p['pos'][1])):
                ind = i
        return ind
        
    def mouseDragEvent(self, ev):
        if ev.button() != QtCore.Qt.LeftButton:
            ev.ignore()
            return
        if ev.isStart():
            pos = ev.buttonDownPos()
            pts = self.scatter.pointsAt(pos)
            if len(pts) == 0:
                ev.ignore()
                return
            self.dragPoint = self._findind(pts[0])
            self.dragOffset = self.points[self.dragPoint]['pos'] - pos
        elif ev.isFinish():
            self.dragPoint = None
            return
        else:
            if self.dragPoint is None:
                ev.ignore()
                return
        self.points[self.dragPoint]['pos'] = ev.pos() + self.dragOffset
        self.setData(points = self.points)
        ev.accept()
        
        #ind = self._findind()

        
class RawDisplayWidget(ImageWidget):
    def __init__(self, stack,parent=None,pointsize = 10):
        super(RawDisplayWidget,self).__init__()
        self.parent = parent
        self.stack = stack
        self.iframe = np.clip(100,0,len(self.stack))
        self.ichan  = 0
        self.warp_im = False
        tmp = self.stack[:np.clip(100,0,len(self.stack))]
        self.levels = np.nanpercentile(tmp,[5,99])
        self._init_ui()
        self._add_hist()
        self.hist.setHistogramRange(*self.levels)
        self.adaptative_histogram = False
        self.allen_show_areas = False
        self.set_image(self.iframe)
        
        if hasattr(self.parent,'allenparwidget'):
            self.allenwidget = self.parent.allenparwidget
            self.points = CustomDragPoints()
            tmp = []
            tmp_text = []
            for i,t in self.allenwidget.landmarks_im.iterrows():
                tmp.append(dict(pos = (t.nx,t.ny),
                                size = pointsize,
                                pen=pg.mkPen(color=t.color)))
                tmp_text.append(t['name'])
            self.points.setData(tmp,tmp_text)
            self.pl.addItem(self.points)
            def update_table():
                # Update the table when points move
                nx = [p['pos'][0] for p in self.points.points]
                ny = [p['pos'][1] for p in self.points.points]
                self.allenwidget.landmarks_im.nx = nx
                self.allenwidget.landmarks_im.ny = ny
                for i,(x,y) in enumerate(zip(nx,ny)):
                    self.allenwidget.table.item(i,4).setText(str(x))
                    self.allenwidget.table.item(i,5).setText(str(y))
            self.points.scatter.sigPlotChanged.connect(update_table)
            self.allenplot = QAllenAreasPlot(plot=self.pl,parent = self)
    def _init_ui(self):
        widget = QWidget()
        slayout = QFormLayout()
        widget.setLayout(slayout)
        self.wframe = QSlider(Qt.Horizontal)
        self.wframe.setValue(0)
        self.wframe.setMaximum(len(self.stack)-1)
        self.wframe.setMinimum(0)
        self.wframe.setSingleStep(1)
        self.wframelabel = QLabel('Frame {0:d}:'.format(self.wframe.value()))
        slayout.addRow(self.wframelabel, self.wframe)
        self.wchan = QSlider(Qt.Horizontal)
        self.wchan.setValue(0)
        self.wchan.setMaximum(self.stack.shape[1]-1)
        self.wchan.setMinimum(0)
        self.wchan.setSingleStep(1)
        self.wchanlabel = QLabel('Channel {0:d}:'.format(self.wchan.value()))
        w1 = QWidget()
        l1 = QHBoxLayout()
        w1.setLayout(l1)
        l1.addWidget(self.wchanlabel)
        l1.addWidget(self.wchan)
        self.wimadapt = QCheckBox()
        l1.addWidget(QLabel('Equalize image:'))
        l1.addWidget(self.wimadapt)
        self.wimwarp = QCheckBox()
        l1.addWidget(QLabel('Warp image:'))
        l1.addWidget(self.wimwarp)
        self.wallen = QCheckBox()
        l1.addWidget(QLabel('Show CCF:'))
        l1.addWidget(self.wallen)

        slayout.addRow(w1)
        self.layout.addRow(widget)
        
        def uhist(val):
            self.adaptative_histogram = val
            self.set_image(redo_levels = True)
        def uwarp(val):
            self.warp_im = val
            self.set_image()
            self.points.set_visible(not val)
            if self.allen_show_areas:
                self.allenplot.update()
        def uallen(val):
            self.allen_show_areas = val
            if val:
                self.allenplot.update()
            else:
                self.allenplot.remove()
        def uframe(val):
            i = self.wframe.value()
            self.wframelabel.setText('Frame {0:d}:'.format(i))
            self.set_image(i)
        def uchan(val):
            self.ichan = self.wchan.value()
            self.wchanlabel.setText('Channel {0:d}:'.format(self.ichan))
            self.set_image()
        
        self.wframe.valueChanged.connect(uframe)
        self.wimadapt.stateChanged.connect(uhist)
        self.wimwarp.stateChanged.connect(uwarp)
        self.wchan.valueChanged.connect(uchan)
        self.wallen.stateChanged.connect(uallen)
       
    def set_image(self,i=None,redo_levels=False):
        if not i is None:
            self.iframe = i
        img = self.stack[self.iframe,self.ichan]
        if self.adaptative_histogram:
            img = im_adapt_hist(img)
        if redo_levels:
            self.levels = np.nanpercentile(img,[5,99])
        if self.warp_im:
            if hasattr(self.parent,'M'):
                img = im_apply_transform(img,self.parent.M)
        self.im.setImage(img,levels = self.levels)
        
        
class SVDDisplayWidget(ImageWidget):
    def __init__(self, stack,parent=None):
        super(SVDDisplayWidget,self).__init__()
        self.parent = parent
        self.stack = stack
        self.warp_im = False
        self.iframe = np.clip(100,0,len(self.stack))
        tmp = self.stack[:np.clip(100,0,len(self.stack))]
        self.levels = np.nanpercentile(tmp,[5,99])
        self._init_ui()
        self._add_hist()
        self.hist.setHistogramRange(*self.levels)
        self.allen_show_areas = False
        self.set_image(self.iframe)
        self.win.scene().sigMouseClicked.connect(self.mouseMoved)    
        
    def _init_ui(self):
        w = QWidget()
        l = QHBoxLayout()
        w.setLayout(l)
        self.wframe = QSlider(Qt.Horizontal)
        self.wframe.setValue(0)
        self.wframe.setMaximum(len(self.stack)-1)
        self.wframe.setMinimum(0)
        self.wframe.setSingleStep(1)
        self.wframelabel = QLabel('Frame {0:d}:'.format(self.wframe.value()))
        l.addWidget(self.wframelabel)
        l.addWidget(self.wframe)
        self.wimwarp = QCheckBox()
        l.addWidget(QLabel('Warp stack:'))
        l.addWidget(self.wimwarp)
        self.wallen = QCheckBox()
        l.addWidget(QLabel('Show CCF:'))
        l.addWidget(self.wallen)
        self.layout.addRow(w)
        def uwarp(val):
            self.warp_im = val
            if hasattr(self.parent,'M'):
                self.stack.set_warped(val,self.parent.M)
            if self.allen_show_areas:
                self.allenplot.update()
            self.set_image()
        def uallen(val):
            self.allen_show_areas = val
            if val:
                if not hasattr(self,'allenplot'):
                    self.allenplot = QAllenAreasPlot(plot=self.pl,parent = self)
                self.allenplot.update()
            else:
                self.allenplot.remove()

        def uframe(val):
            i = self.wframe.value()
            self.wframelabel.setText('Frame {0:d}:'.format(i))
            self.set_image(i)
            self.parent.roiwidget.p1.setRange(xRange=self.parent.roiwidget.xlim+i)
            self.parent.roiwidget.line.setPos((i,0))
        self.wframe.valueChanged.connect(uframe)
        self.wimwarp.stateChanged.connect(uwarp)
        self.wallen.stateChanged.connect(uallen)

    def set_image(self,i=None):
        if not i is None:
            self.iframe = i
        img = self.stack[self.iframe]
        self.im.setImage(img,levels = self.levels)
        
    def get_xy(self,x,y):
        x = int(np.clip(x,0,self.stack.shape[1]))
        y = int(np.clip(y,0,self.stack.shape[2]))
        idx = np.ravel_multi_index((x,y),self.stack.shape[1:])
        t = np.dot(self.stack.Uflat[idx,:],self.stack.SVT)
        return t

    def mouseMoved(self,pos):
        modifiers = QApplication.keyboardModifiers()
        pos = self.im.mapFromScene(pos.scenePos())
        if bool(modifiers == Qt.ControlModifier):
            self.parent.roiwidget.add_roi((pos.x(),pos.y()))

class SVDViewer(QMainWindow):
    def __init__(self,stack, folder = None, raw = None, landmarks_file = None, trial_onsets = None):
        super(SVDViewer,self).__init__()
        self.setWindowTitle('wfield')
        self.folder = folder
        if self.folder is None:
            self.folder = os.path.abspath(os.path.curdir)
        self.stack = stack
        self.trial_onsets = trial_onsets
        self.raw = raw
        self.trial_mask = np.ones((self.stack.SVT.shape[-1]),dtype=bool)
        if not self.trial_onsets is None:
            self.trial_mask[self.trial_onsets[:,1]] = False
        self.setDockOptions(QMainWindow.AllowTabbedDocks |
                            QMainWindow.AllowNestedDocks |
                            QMainWindow.AnimatedDocks)

        
        self.displaywidget = SVDDisplayWidget( self.stack,parent = self)
        self.roiwidget = ROIPlotWidget(stack,self.displaywidget.pl,self.displaywidget.im,
                                       trial_mask = self.trial_mask)
        self.localcorrwidget = LocalCorrelationWidget(stack)
        
        if not self.raw is None:
            self.allenparwidget = AllenMatchTable(landmarks_file = landmarks_file,
                                                  parent = self) 
            self.rawwidget = RawDisplayWidget(raw,parent = self)
            
        self.svdtab = QDockWidget('Reconstructed')
        self.svdtab.setWidget(self.displaywidget)
        self.addDockWidget(Qt.RightDockWidgetArea,self.svdtab)        
        # Pixel correlation 
        self.lcorrtab = QDockWidget('Pixel correlation')
        self.lcorrtab.setWidget(self.localcorrwidget)
        self.addDockWidget(Qt.RightDockWidgetArea,self.lcorrtab)
        self.tabifyDockWidget(self.lcorrtab,self.svdtab)
        # Raw data
        if not raw is None:
            self.rawtab = QDockWidget('Raw data')
            self.rawtab.setWidget(self.rawwidget)
            self.addDockWidget(Qt.RightDockWidgetArea,self.rawtab)
            self.tabifyDockWidget(self.svdtab,self.rawtab)

        self.roitab = QDockWidget("ROI", self)
        self.roitab.setWidget(self.roiwidget)
        self.addDockWidget(Qt.BottomDockWidgetArea,self.roitab)
        self.set_dock(self.roitab,False)
        # Allen match
        if hasattr(self,'allenparwidget'):
            self.allenpartab = QDockWidget('CCF match parameters')
            self.allenpartab.setWidget(self.allenparwidget)
            self.addDockWidget(Qt.BottomDockWidgetArea,self.allenpartab)
            self.tabifyDockWidget(self.allenpartab,self.roitab)        
        self.show()

    def set_dock(self,dock,floating=False):
        dock.setAllowedAreas(Qt.LeftDockWidgetArea |
                             Qt.RightDockWidgetArea |
                             Qt.BottomDockWidgetArea |
                             Qt.TopDockWidgetArea)
        dock.setFeatures(QDockWidget.DockWidgetMovable |
                         QDockWidget.DockWidgetFloatable)
        dock.setFloating(floating)

class LocalCorrelationWidget(ImageWidget):
    def __init__(self, stack,parent=None):
        super(LocalCorrelationWidget,self).__init__()
        self.parent = parent
        self.stack = stack
        U = stack.U
        SVT = stack.SVT
        from .utils_svd import svd_pix_correlation
        self.localcorr = svd_pix_correlation(U,SVT,
                                             norm_svt=True)
        self.levels = [0,1.]
        
        pos = np.array([0, 0.5, 1.])
        color = np.array([[0,0,255,255], [255,255,255,255], [255,0,0,255]], dtype=np.ubyte)
        cmap = pg.ColorMap(pos, color)
        lut = cmap.getLookupTable(0, 1.0, 256)

        self._add_hist()
        self.hist.gradient.setColorMap(cmap)
        self.hist.setHistogramRange(*self.levels)

        self.set_image([0,0])
        self.win.scene().sigMouseMoved.connect(self.mouseMoved)
        
    def set_image(self,xy=[0,0]):
        img = (self.localcorr.get(*xy)+1)/2.
        self.im.setImage(img,levels = self.levels)

    def mouseMoved(self,pos):
        modifiers = QApplication.keyboardModifiers()
        pos = self.im.mapFromScene(pos)
        if bool(modifiers == Qt.ControlModifier):
            self.set_image((int(pos.y()),int(pos.x())))

class ROIPlotWidget(QWidget):
    colors = ['#d62728',
          '#1f77b4',
          '#ff7f0e',
          '#2ca02c',
          '#9467bd',
          '#8c564b',
          '#e377c2',
          '#7f7f7f',
          '#bcbd22']
    penwidth = 1
    def __init__(self,stack, roi_target= None,view=None,npoints = 500,trial_mask = None):
        super(ROIPlotWidget,self).__init__()	
        layout = QGridLayout()
        self.stack = stack
        self.setLayout(layout)
        self.view = view
        self.roi_target = roi_target
        self.trial_mask = trial_mask
        if self.trial_mask is None:
            self.trial_mask = 'finite'
        win = pg.GraphicsLayoutWidget(parent=self)
        self.p1 = win.addPlot()
        self.p1.getAxis('bottom').setPen(axiscolor) 
        self.p1.getAxis('left').setPen(axiscolor) 
        layout.addWidget(win,0,0)
        self.line = pg.InfiniteLine(angle = 90,movable = True)
        self.p1.addItem(self.line)
        self.xlim = np.array([0,1000])
        self.N = npoints
        self.rois = []
        self.plots = []
        self.buffers = []
        self.time = np.arange(self.stack.shape[0],dtype='float32')
        self.offset = 0.1
    def add_roi(self,pos):
        pencolor = self.colors[
            np.mod(len(self.plots),len(self.colors))]
        self.rois.append(pg.RectROI(pos=pos,
                                    size=20,
                                    pen=pencolor))
        self.plots.append(pg.PlotCurveItem(pen=pg.mkPen(
            color=pencolor,width=self.penwidth)))
        self.p1.addItem(self.plots[-1])
        self.roi_target.addItem(self.rois[-1])
        self.update(len(self.rois)-1)
        self.rois[-1].sigRegionChanged.connect(partial(self.update,i=len(self.rois)-1))

    def items(self):
        return self.rois
    def closeEvent(self,ev):
        for roi in self.rois:
            self.roi_target.removeItem(roi)
        ev.accept()
    def update(self,i):
        X = np.zeros(self.stack.shape[1:],dtype='uint8')
        r = self.rois[i].getArraySlice(X, self.view,axes=(0,1))
        X[r[0][0],r[0][1]]=1
        idx = np.ravel_multi_index(np.where(X==1),self.stack.shape[1:])
        t = np.nanmean(np.dot(self.stack.Uflat[idx,:],
                              self.stack.SVT),
                    axis=0).astype('float32')
        t[0] = t[1]
        self.plots[i].setData(x = self.time,
                              y = t+self.offset*i,connect=self.trial_mask)



