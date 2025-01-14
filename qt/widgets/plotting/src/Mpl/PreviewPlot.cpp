// Mantid Repository : https://github.com/mantidproject/mantid
//
// Copyright &copy; 2019 ISIS Rutherford Appleton Laboratory UKRI,
//     NScD Oak Ridge National Laboratory, European Spallation Source
//     & Institut Laue - Langevin
// SPDX - License - Identifier: GPL - 3.0 +
#include "MantidQtWidgets/Plotting/Mpl/PreviewPlot.h"
#include "MantidAPI/MatrixWorkspace.h"
#include "MantidKernel/Logger.h"
#include "MantidQtWidgets/MplCpp/ColorConverter.h"
#include "MantidQtWidgets/MplCpp/FigureCanvasQt.h"
#include "MantidQtWidgets/MplCpp/MantidAxes.h"

#include <QAction>
#include <QContextMenuEvent>
#include <QEvent>
#include <QMenu>
#include <QTimer>
#include <QVBoxLayout>

#include <algorithm>

using Mantid::API::AnalysisDataService;
using Mantid::API::MatrixWorkspace;
using MantidQt::Widgets::MplCpp::Artist;
using MantidQt::Widgets::MplCpp::ColorConverter;
using MantidQt::Widgets::MplCpp::Figure;
using MantidQt::Widgets::MplCpp::FigureCanvasQt;
using MantidQt::Widgets::MplCpp::Line2D;
using MantidQt::Widgets::MplCpp::MantidAxes;
namespace Python = MantidQt::Widgets::Common::Python;

namespace {
Mantid::Kernel::Logger g_log("PreviewPlot");
constexpr auto MANTID_PROJECTION = "mantid";
constexpr auto DRAGGABLE_LEGEND = true;
constexpr auto PLOT_TOOL_NONE = "None";
constexpr auto PLOT_TOOL_PAN = "Pan";
constexpr auto PLOT_TOOL_ZOOM = "Zoom";
constexpr auto LINEAR_SCALE = "Linear";
constexpr auto LOG_SCALE = "Log";
constexpr auto SQUARE_SCALE = "Square";

} // namespace

namespace MantidQt {

namespace MantidWidgets {

/**
 * Construct a plot object
 * @param parent The parent widget
 * @param watchADS If true then ADS observers are added
 */
PreviewPlot::PreviewPlot(QWidget *parent, bool observeADS)
    : QWidget(parent), m_canvas{new FigureCanvasQt(111, MANTID_PROJECTION,
                                                   parent)},
      m_panZoomTool(m_canvas),
      m_wsRemovedObserver(*this, &PreviewPlot::onWorkspaceRemoved),
      m_wsReplacedObserver(*this, &PreviewPlot::onWorkspaceReplaced) {
  createLayout();
  createActions();

  m_selectorActive = false;

  m_canvas->installEventFilterToMplCanvas(this);
  watchADS(observeADS);
}

/**
 * Destructor.
 * Removes ADS observers
 */
PreviewPlot::~PreviewPlot() { watchADS(false); }

/**
 * Enable/disable the ADS observers
 * @param on If true ADS observers are enabled else they are disabled
 */
void PreviewPlot::watchADS(bool on) {
  auto &notificationCenter = AnalysisDataService::Instance().notificationCenter;
  if (on) {
    notificationCenter.addObserver(m_wsRemovedObserver);
    notificationCenter.addObserver(m_wsReplacedObserver);
  } else {
    notificationCenter.removeObserver(m_wsReplacedObserver);
    notificationCenter.removeObserver(m_wsRemovedObserver);
  }
}

/**
 * Gets the canvas used by the preview plot
 * @return The canvas
 */
Widgets::MplCpp::FigureCanvasQt *PreviewPlot::canvas() const {
  return m_canvas;
}

/**
 * Converts the QPoint in pixels to axes coordinates
 * @return The axes coordinates of the QPoint
 */
QPointF PreviewPlot::toDataCoords(const QPoint &point) const {
  return m_canvas->toDataCoords(point);
}

/**
 * Add a line for a given spectrum to the plot
 * @param lineName A string label for the line
 * @param ws A MatrixWorkspace that contains the data
 * @param wsIndex The index of the workspace to access
 * @param lineColour Defines the color of the line
 */
void PreviewPlot::addSpectrum(const QString &lineName,
                              const Mantid::API::MatrixWorkspace_sptr &ws,
                              const size_t wsIndex, const QColor &lineColour,
                              const QHash<QString, QVariant> &plotKwargs) {
  if (lineName.isEmpty()) {
    g_log.warning("Cannot plot with empty line name");
    return;
  }
  if (!ws) {
    g_log.warning("Cannot plot null workspace");
    return;
  }
  removeSpectrum(lineName);

  auto axes = m_canvas->gca<MantidAxes>();
  if (linesWithErrors().contains(lineName)) {
    axes.errorbar(ws, wsIndex, lineColour.name(QColor::HexRgb), lineName,
                  plotKwargs);
  } else {
    m_lines[lineName] = false;
    axes.plot(ws, wsIndex, lineColour.name(QColor::HexRgb), lineName,
              plotKwargs);
  }

  regenerateLegend();
  axes.relim();

  emit resetSelectorBounds();
  replot();
}

/**
 * Add a line for a given spectrum to the plot
 * @param lineName A string label for the line
 * @param wsName A name of a MatrixWorkspace that contains the data
 * @param wsIndex The index of the workspace to access
 * @param lineColour Defines the color of the line
 */
void PreviewPlot::addSpectrum(const QString &lineName, const QString &wsName,
                              const size_t wsIndex, const QColor &lineColour,
                              const QHash<QString, QVariant> &plotKwargs) {
  addSpectrum(lineName,
              AnalysisDataService::Instance().retrieveWS<MatrixWorkspace>(
                  wsName.toStdString()),
              wsIndex, lineColour, plotKwargs);
}

/**
 * Remove the named line from the plot
 * @param lineName A name of a given line on the plot. If the lineName is
 * not known then this does nothing
 */
void PreviewPlot::removeSpectrum(const QString &lineName) {
  auto axes = m_canvas->gca();
  axes.removeArtists("lines", lineName);
  m_lines.remove(lineName);
}

/**
 * Add a range selector to a preview plot
 * @param name The name to give the range selector
 * @param type The type of the range selector
 * @return The range selector
 */
RangeSelector *PreviewPlot::addRangeSelector(const QString &name,
                                             RangeSelector::SelectType type) {
  if (m_rangeSelectors.contains(name))
    throw std::runtime_error("RangeSelector already exists on PreviewPlot.");

  m_rangeSelectors[name] = new MantidWidgets::RangeSelector(this, type);
  return m_rangeSelectors[name];
}

/**
 * Gets a range selector from the PreviewPlot
 * @param name The name of the range selector
 * @return The range selector
 */
RangeSelector *PreviewPlot::getRangeSelector(const QString &name) const {
  if (!m_rangeSelectors.contains(name))
    throw std::runtime_error("RangeSelector was not found on PreviewPlot.");
  return m_rangeSelectors[name];
}

/**
 * Add a single selector to a preview plot
 * @param name The name to give the single selector
 * @param type The type of the single selector
 * @return The single selector
 */
SingleSelector *PreviewPlot::addSingleSelector(const QString &name,
                                               SingleSelector::SelectType type,
                                               double position) {
  if (m_singleSelectors.contains(name))
    throw std::runtime_error("SingleSelector already exists on PreviewPlot.");

  m_singleSelectors[name] =
      new MantidWidgets::SingleSelector(this, type, position);
  return m_singleSelectors[name];
}

/**
 * Gets a single selector from the PreviewPlot
 * @param name The name of the single selector
 * @return The single selector
 */
SingleSelector *PreviewPlot::getSingleSelector(const QString &name) const {
  if (!m_singleSelectors.contains(name))
    throw std::runtime_error("SingleSelector was not found on PreviewPlot.");
  return m_singleSelectors[name];
}

/**
 * Set whether or not one of the selectors on the preview plot is being moved or
 * not. This is required as we only want the user to be able to move one marker
 * at a time, otherwise the markers could get 'stuck' together.
 * @param active True if a selector is being moved.
 */
void PreviewPlot::setSelectorActive(bool active) { m_selectorActive = active; }

/**
 * Returns True if a selector is currently being moved on the preview plot.
 * @return True if a selector is currently being moved on the preview plot.
 */
bool PreviewPlot::selectorActive() const { return m_selectorActive; }

/**
 * Set the range of the specified axis
 * @param range The new range
 * @param axisID An enumeration defining the axis
 */
void PreviewPlot::setAxisRange(const QPair<double, double> &range,
                               AxisID axisID) {
  switch (axisID) {
  case AxisID::XBottom:
    m_canvas->gca().setXLim(range.first, range.second);
    break;
  case AxisID::YLeft:
    m_canvas->gca().setYLim(range.first, range.second);
    break;
  }
}

/**
 * Gets the range of the specified axis
 * @param axisID An enumeration defining the axis
 * @return The axis range
 */
std::tuple<double, double> PreviewPlot::getAxisRange(AxisID axisID) {
  switch (axisID) {
  case AxisID::XBottom:
    return m_canvas->gca().getXLim();
  case AxisID::YLeft:
    return m_canvas->gca().getYLim();
  }
  throw std::runtime_error(
      "Incorrect AxisID provided. Axis types are XBottom and YLeft");
}

void PreviewPlot::replot() {
  m_canvas->draw();
  emit redraw();
}

/**
 * Clear all lines from the plot
 */
void PreviewPlot::clear() { m_canvas->gca().clear(); }

/**
 * Resize the X axis to encompass all of the data
 */
void PreviewPlot::resizeX() { m_canvas->gca().autoscaleView(true, false); }

/**
 * Reset the whole view to show all of the data
 */
void PreviewPlot::resetView() {
  m_panZoomTool.zoomOut();
  if (!m_panZoomTool.isPanEnabled() && !m_panZoomTool.isZoomEnabled())
    QTimer::singleShot(0, this, SLOT(replot()));
}

/**
 * Set the face colour for the canvas
 * @param colour A new colour for the figure facecolor
 */
void PreviewPlot::setCanvasColour(QColor colour) {
  m_canvas->gcf().setFaceColor(colour);
}

/**
 * @brief PreviewPlot::setLinesWithErrors
 * @param labels A list of line labels where error bars should be shown
 */
void PreviewPlot::setLinesWithErrors(QStringList labels) {
  for (const QString &label : labels) {
    m_lines[label] = true;
  }
}

/**
 * Toggle for programatic legend visibility toggle
 * @param visible If True the legend is visible on the canvas
 */
void PreviewPlot::showLegend(bool visible) {
  m_contextLegend->setChecked(visible);
}

/**
 * @return The current colour of the canvas
 */
QColor PreviewPlot::canvasColour() const { return m_canvas->gcf().faceColor(); }

/**
 * Capture events destined for the canvas
 * @param watched Target object (Unused)
 * @param evt A pointer to the event object
 * @return True if the event should be stopped, false otherwise
 */
bool PreviewPlot::eventFilter(QObject *watched, QEvent *evt) {
  Q_UNUSED(watched);
  bool stopEvent{false};
  switch (evt->type()) {
  case QEvent::ContextMenu:
    // handled by mouse press events below as we need to
    // stop the canvas getting mouse events in some circumstances
    // to disable zooming/panning
    stopEvent = true;
    break;
  case QEvent::MouseButtonPress:
    stopEvent = handleMousePressEvent(static_cast<QMouseEvent *>(evt));
    break;
  case QEvent::MouseButtonRelease:
    stopEvent = handleMouseReleaseEvent(static_cast<QMouseEvent *>(evt));
    break;
  case QEvent::MouseMove:
    stopEvent = handleMouseMoveEvent(static_cast<QMouseEvent *>(evt));
    break;
  case QEvent::Resize:
    stopEvent = handleWindowResizeEvent();
    break;
  default:
    break;
  }
  return stopEvent;
}

/**
 * Handler called when the event filter recieves a mouse press event
 * @param evt A pointer to the event
 * @return True if the event propagation should be stopped, false otherwise
 */
bool PreviewPlot::handleMousePressEvent(QMouseEvent *evt) {
  bool stopEvent(false);
  // right-click events are reserved for the context menu
  // show when the mouse click is released
  if (evt->buttons() & Qt::RightButton) {
    stopEvent = true;
  } else if (evt->buttons() & Qt::LeftButton) {
    const auto position = evt->pos();
    if (!position.isNull())
      emit mouseDown(position);
  }
  return stopEvent;
}

/**
 * Handler called when the event filter recieves a mouse release event
 * @param evt A pointer to the event
 * @return True if the event propagation should be stopped, false otherwise
 */
bool PreviewPlot::handleMouseReleaseEvent(QMouseEvent *evt) {
  bool stopEvent(false);
  if (evt->button() == Qt::RightButton) {
    stopEvent = true;
    showContextMenu(evt);
  } else if (evt->button() == Qt::LeftButton) {
    const auto position = evt->pos();
    if (!position.isNull())
      emit mouseUp(position);
    QTimer::singleShot(0, this, SLOT(replot()));
  }
  return stopEvent;
}

/**
 * Handler called when the event filter recieves a mouse move event
 * @param evt A pointer to the event
 * @return True if the event propagation should be stopped, false otherwise
 */
bool PreviewPlot::handleMouseMoveEvent(QMouseEvent *evt) {
  bool stopEvent(false);
  if (evt->buttons() == Qt::LeftButton) {
    const auto position = evt->pos();
    if (!position.isNull())
      emit mouseMove(position);
  }
  return stopEvent;
}

/**
 * Handler called when the event filter recieves a window resize event
 * @return True if the event propagation should be stopped, false otherwise
 */
bool PreviewPlot::handleWindowResizeEvent() {
  QTimer::singleShot(0, this, SLOT(replot()));
  return false;
}

/**
 * Display the context menu for the canvas
 */
void PreviewPlot::showContextMenu(QMouseEvent *evt) {
  QMenu contextMenu{this};
  auto plotTools = contextMenu.addMenu("Plot Tools");
  plotTools->addActions(m_contextPlotTools->actions());
  contextMenu.addAction(m_contextResetView);

  contextMenu.addSeparator();
  auto xscale = contextMenu.addMenu("X Scale");
  xscale->addActions(m_contextXScale->actions());
  auto yScale = contextMenu.addMenu("Y Scale");
  yScale->addActions(m_contextYScale->actions());

  contextMenu.addSeparator();
  contextMenu.addAction(m_contextLegend);

  contextMenu.exec(evt->globalPos());
}

/**
 * Initialize the layout for the widget
 */
void PreviewPlot::createLayout() {
  auto plotLayout = new QVBoxLayout(this);
  plotLayout->setContentsMargins(0, 0, 0, 0);
  plotLayout->setSpacing(0);
  plotLayout->addWidget(m_canvas, 0, 0);
  setLayout(plotLayout);
}

/**
 * Create the menu actions items
 */
void PreviewPlot::createActions() {
  // Create an exclusive group of checkable actions with
  auto createExclusiveActionGroup =
      [this](const std::initializer_list<const char *> &names) {
        auto group = new QActionGroup(this);
        group->setExclusive(true);
        for (const auto &name : names) {
          auto action = group->addAction(name);
          action->setCheckable(true);
        }
        group->actions()[0]->setChecked(true);
        return group;
      };
  // plot tools
  m_contextPlotTools = createExclusiveActionGroup(
      {PLOT_TOOL_NONE, PLOT_TOOL_PAN, PLOT_TOOL_ZOOM});
  connect(m_contextPlotTools, &QActionGroup::triggered, this,
          &PreviewPlot::switchPlotTool);
  m_contextResetView = new QAction("Reset Plot", this);
  connect(m_contextResetView, &QAction::triggered, this,
          &PreviewPlot::resetView);

  // scales
  m_contextXScale =
      createExclusiveActionGroup({LINEAR_SCALE, LOG_SCALE, SQUARE_SCALE});
  connect(m_contextXScale, &QActionGroup::triggered, this,
          &PreviewPlot::setXScaleType);
  m_contextYScale = createExclusiveActionGroup({LINEAR_SCALE, LOG_SCALE});
  connect(m_contextYScale, &QActionGroup::triggered, this,
          &PreviewPlot::setYScaleType);
  m_contextXScale->actions()[0]->setChecked(true);
  m_contextYScale->actions()[0]->setChecked(true);

  // legend
  m_contextLegend = new QAction("Legend", this);
  m_contextLegend->setCheckable(true);
  m_contextLegend->setChecked(true);
  connect(m_contextLegend, &QAction::toggled, this, &PreviewPlot::toggleLegend);
}

/**
 * @return True if the legend is visible, false otherwise
 */
bool PreviewPlot::legendIsVisible() const {
  return m_contextLegend->isChecked();
}

/**
 * @return True if the PreviewPlot has a line with the specified name
 */
bool PreviewPlot::hasCurve(const QString &lineName) const {
  return m_lines.contains(lineName);
}

/**
 * @return A list of labels whose line have errors attached
 */
QStringList PreviewPlot::linesWithErrors() const {
  QStringList visibleErrorLabels;
  auto iterator = m_lines.constBegin();
  while (iterator != m_lines.constEnd()) {
    if (iterator.value())
      visibleErrorLabels.append(iterator.key());
    ++iterator;
  }
  return visibleErrorLabels;
}

/**
 * Observer method called when a workspace is removed from the ADS
 * @param nf A pointer to the notification object
 */
void PreviewPlot::onWorkspaceRemoved(
    Mantid::API::WorkspacePreDeleteNotification_ptr nf) {
  // Ignore non matrix workspaces
  if (auto ws = boost::dynamic_pointer_cast<MatrixWorkspace>(nf->object())) {
    // the artist may have already been removed. ignore the event is that is the
    // case
    try {
      m_canvas->gca<MantidAxes>().removeWorkspaceArtists(ws);
    } catch (Mantid::PythonInterface::PythonException &) {
    }
    this->replot();
  }
}

/**
 * Observer method called when a workspace is replaced in the ADS
 * @param nf A pointer to the notification object
 */
void PreviewPlot::onWorkspaceReplaced(
    Mantid::API::WorkspaceBeforeReplaceNotification_ptr nf) {
  // Ignore non matrix workspaces
  if (auto oldWS =
          boost::dynamic_pointer_cast<MatrixWorkspace>(nf->oldObject())) {
    if (auto newWS =
            boost::dynamic_pointer_cast<MatrixWorkspace>(nf->newObject())) {
      m_canvas->gca<MantidAxes>().replaceWorkspaceArtists(newWS);
      this->replot();
    }
  }
}

/**
 * If the legend is visible regenerate it based on the current content
 */
void PreviewPlot::regenerateLegend() {
  if (legendIsVisible()) {
    m_canvas->gca().legend(DRAGGABLE_LEGEND);
  }
}

/**
 * If the legend is visible remove it from the canvas
 */
void PreviewPlot::removeLegend() {
  auto legend = m_canvas->gca().legendInstance();
  if (!legend.pyobj().is_none()) {
    m_canvas->gca().legendInstance().remove();
  }
}

/**
 * Called when a different plot tool is selected. Enables the
 * appropriate mode on the canvas
 * @param selected A QAction pointer denoting the desired tool
 */
void PreviewPlot::switchPlotTool(QAction *selected) {
  QString toolName = selected->text();
  if (toolName == PLOT_TOOL_NONE) {
    m_panZoomTool.enableZoom(false);
    m_panZoomTool.enablePan(false);
    replot();
  } else if (toolName == PLOT_TOOL_PAN) {
    m_panZoomTool.enablePan(true);
    m_canvas->draw();
  } else if (toolName == PLOT_TOOL_ZOOM) {
    m_panZoomTool.enableZoom(true);
    m_canvas->draw();
  } else {
    // if a tool is added to the menu but no handler is added
    g_log.warning("Unknown plot tool selected.");
  }
}

/**
 * Set the X scale based on the given QAction
 * @param selected The action that triggered the slot
 */
void PreviewPlot::setXScaleType(QAction *selected) {
  setScaleType(AxisID::XBottom, selected->text());
}

/**
 * Set the X scale based on the given QAction
 * @param selected The action that triggered the slot
 */
void PreviewPlot::setYScaleType(QAction *selected) {
  setScaleType(AxisID::YLeft, selected->text());
}

void PreviewPlot::setScaleType(AxisID id, QString actionName) {
  auto scaleType = actionName.toLower().toLatin1();
  auto axes = m_canvas->gca();
  switch (id) {
  case AxisID::XBottom:
    axes.setXScale(scaleType.constData());
    break;
  case AxisID::YLeft:
    axes.setYScale(scaleType.constData());
    break;
  default:
    break;
  }
  this->replot();
}

/**
 * Toggle the legend visibility state
 * @param checked True if the state should be visible, false otherwise
 */
void PreviewPlot::toggleLegend(const bool checked) {
  if (checked) {
    regenerateLegend();
  } else {
    removeLegend();
  }
  this->replot();
}

} // namespace MantidWidgets
} // namespace MantidQt
