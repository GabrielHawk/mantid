# Mantid Repository : https://github.com/mantidproject/mantid
#
# Copyright &copy; 2017 ISIS Rutherford Appleton Laboratory UKRI,
#     NScD Oak Ridge National Laboratory, European Spallation Source
#     & Institut Laue - Langevin
# SPDX - License - Identifier: GPL - 3.0 +
#  This file is part of the mantid workbench.
#
#
"""Defines a collection of functions to support plotting workspaces with
our custom window.
"""

# std imports
import collections
import math
import numpy as np

# 3rd party imports
try:
    from matplotlib.cm import viridis as DEFAULT_CMAP
except ImportError:
    from matplotlib.cm import jet as DEFAULT_CMAP
from matplotlib.gridspec import GridSpec
from matplotlib.legend import Legend

# local imports
from mantid.api import AnalysisDataService, MatrixWorkspace
from mantid.kernel import Logger
from mantid.plots import MantidAxes
from mantidqt.plotting.figuretype import figure_type, FigureType
from mantid.py3compat import is_text_string, string_types
from mantidqt.dialogs.spectraselectorutils import get_spectra_selection

# -----------------------------------------------------------------------------
# Constants
# -----------------------------------------------------------------------------
PROJECTION = 'mantid'
# See https://matplotlib.org/api/_as_gen/matplotlib.figure.SubplotParams.html#matplotlib.figure.SubplotParams
SUBPLOT_WSPACE = 0.5
SUBPLOT_HSPACE = 0.5
LOGGER = Logger("workspace.plotting.functions")


# -----------------------------------------------------------------------------
# Decorators
# -----------------------------------------------------------------------------

def manage_workspace_names(func):
    """
    A decorator to go around plotting functions.
    This will retrieve workspaces from workspace names before
    calling the plotting function
    :param func: A plotting function
    :return:
    """

    def inner_func(workspaces, *args, **kwargs):
        workspaces = _validate_workspace_names(workspaces)
        return func(workspaces, *args, **kwargs)

    return inner_func


# -----------------------------------------------------------------------------
# 'Public' Functions
# -----------------------------------------------------------------------------

def can_overplot():
    """
    Checks if overplotting on the current figure can proceed
    with the given options

    :return: A 2-tuple of boolean indicating compatability and
    a string containing an error message if the current figure is not
    compatible.
    """
    compatible = False
    msg = "Unable to overplot on currently active plot type.\n" \
          "Please select another plot."
    fig = current_figure_or_none()
    if fig is not None:
        figtype = figure_type(fig)
        if figtype is FigureType.Line or figtype is FigureType.Errorbar:
            compatible, msg = True, None

    return compatible, msg


def current_figure_or_none():
    """If an active figure exists then return it otherwise return None

    :return: An active figure or None
    """
    import matplotlib.pyplot as plt
    if len(plt.get_fignums()) > 0:
        return plt.gcf()
    else:
        return None


def figure_title(workspaces, fig_num):
    """Create a default figure title from a single workspace, list of workspaces or
    workspace names and a figure number. The name of the first workspace in the list
    is concatenated with the figure number.

    :param workspaces: A single workspace, list of workspaces or workspace name/list of workspace names
    :param fig_num: An integer denoting the figure number
    :return: A title for the figure
    """

    def wsname(w):
        return w.name() if hasattr(w, 'name') else w

    if is_text_string(workspaces) or not isinstance(workspaces, collections.Sequence):
        # assume a single workspace
        first = workspaces
    else:
        assert len(workspaces) > 0
        first = workspaces[0]

    return wsname(first) + '-' + str(fig_num)


def plot_from_names(names, errors, overplot, fig=None, show_colorfill_btn=False):
    """
    Given a list of names of workspaces, raise a dialog asking for the
    a selection of what to plot and then plot it.

    :param names: A list of workspace names
    :param errors: If true then error bars will be plotted on the points
    :param overplot: If true then the add to the current figure if one
                     exists and it is a compatible figure
    :param fig: If not None then use this figure object to plot
    :return: The figure containing the plot or None if selection was cancelled
    """
    workspaces = AnalysisDataService.Instance().retrieveWorkspaces(names, unrollGroups=True)
    try:
        selection = get_spectra_selection(workspaces, show_colorfill_btn=show_colorfill_btn, overplot=overplot)
    except Exception as exc:
        LOGGER.warning(format(str(exc)))
        selection = None

    if selection is None:
        return None
    elif selection == 'colorfill':
        return pcolormesh_from_names(names)

    return plot(selection.workspaces, spectrum_nums=selection.spectra,
                wksp_indices=selection.wksp_indices,
                errors=errors, overplot=overplot, fig=fig, tiled=selection.plot_type==selection.Tiled)


def get_plot_fig(overplot=None, ax_properties=None, window_title=None, axes_num=1, fig=None):
    """
    Create a blank figure and axes, with configurable properties.
    :param overplot: If true then plotting on figure will plot over previous plotting. If an axis object the overplotting
    will be done on the axis passed in
    :param ax_properties: A dict of axes properties. E.g. {'yscale': 'log'} for log y-axis
    :param window_title: A string denoting the name of the GUI window which holds the graph
    :param axes_num: The number of axes to create on the figure
    :param fig: An optional figure object
    :return: Matplotlib fig and axes objects
    """
    import matplotlib.pyplot as plt
    if fig and overplot:
        fig = fig
    elif fig:
        fig, _, _, _ = _create_subplots(axes_num, fig)
    elif overplot:
        fig = plt.gcf()
    else:
        fig, _, _, _ = _create_subplots(axes_num)

    if ax_properties:
        for axis in fig.axes:
            axis.set(**ax_properties)
    if window_title:
        fig.canvas.set_window_title(window_title)

    return fig, fig.axes


@manage_workspace_names
def plot(workspaces, spectrum_nums=None, wksp_indices=None, errors=False,
         overplot=False, fig=None, plot_kwargs=None, ax_properties=None,
         window_title=None, tiled=False):
    """
    Create a figure with a single subplot and for each workspace/index add a
    line plot to the new axes. show() is called before returning the figure instance. A legend
    is added.

    :param workspaces: A list of workspace handles or strings
    :param spectrum_nums: A list of spectrum number identifiers (general start from 1)
    :param wksp_indices: A list of workspace indexes (starts from 0)
    :param errors: If true then error bars are added for each plot
    :param overplot: If true then overplot over the current figure if one exists. If an axis object the overplotting
    will be done on the axis passed in
    :param fig: If not None then use this Figure object to plot
    :param plot_kwargs: Arguments that will be passed onto the plot function
    :param ax_properties: A dict of axes properties. E.g. {'yscale': 'log'}
    :param window_title: A string denoting name of the GUI window which holds the graph
    :param tiled: An optional flag controlling whether to do a tiled or overlayed plot
    :return: The figure containing the plots
    """
    if plot_kwargs is None:
        plot_kwargs = {}
    _validate_plot_inputs(workspaces, spectrum_nums, wksp_indices, tiled, overplot)

    if spectrum_nums is not None:
        kw, nums = 'specNum', spectrum_nums
    else:
        kw, nums = 'wkspIndex', wksp_indices

    num_axes = len(workspaces) * len(nums) if tiled else 1

    fig, axes = get_plot_fig(overplot, ax_properties, window_title, num_axes, fig)

    # Convert to a MantidAxes if it isn't already. Ignore legend since
    # a new one will be drawn later
    axes = [MantidAxes.from_mpl_axes(ax, ignore_artists=[Legend]) if not isinstance(ax, MantidAxes) else ax
            for ax in axes]

    if tiled:
        ws_index = [(ws, index) for ws in workspaces for index in nums]
        for index, ax in enumerate(axes):
            if index < len(ws_index):
                _do_single_plot(ax, [ws_index[index][0]], errors, False, [ws_index[index][1]], kw, plot_kwargs)
            else:
                ax.axis('off')
    else:
        ax = overplot if isinstance(overplot, MantidAxes) else axes[0]
        ax.axis('on')
        _do_single_plot(ax, workspaces, errors, not overplot, nums, kw, plot_kwargs)

    if not overplot:
        fig.canvas.set_window_title(figure_title(workspaces, fig.number))
    # This updates the toolbar so the home button now takes you back to this point, the try catch is in case the manager does not
    # have a toolbar attatched.
    try:
        fig.canvas.manager.toolbar.update()
    except AttributeError:
        pass
    fig.canvas.draw()
    fig.show()
    return fig


def _do_single_plot(ax, workspaces, errors, set_title, nums, kw, plot_kwargs):
    # do the plotting
    plot_fn = ax.errorbar if errors else ax.plot
    for ws in workspaces:
        for num in nums:
            plot_kwargs[kw] = num
            plot_fn(ws, **plot_kwargs)

    ax.legend().draggable()
    if set_title:
        title = workspaces[0].name()
        ax.set_title(title)


def pcolormesh_from_names(names, fig=None, ax=None):
    """
    Create a figure containing pcolor subplots

    :param names: A list of workspace names
    :param fig: An optional figure to contain the new plots. Its current contents will be cleared
    :param ax: An optional axis instance on which to put new plots. It's current contents will be cleared
    :returns: The figure containing the plots
    """
    try:
        if ax:
            pcolormesh_on_axis(ax, AnalysisDataService.retrieve(names[0]))
            fig.canvas.draw()
            fig.show()
            return fig
        else:
            return pcolormesh(AnalysisDataService.retrieveWorkspaces(names, unrollGroups=True),
                              fig=fig)
    except Exception as exc:
        LOGGER.warning(format(str(exc)))
        return None


def use_imshow(ws):
    y = ws.getAxis(1).extractValues()
    difference = np.diff(y)
    try:
        commonLogBins = hasattr(ws, 'isCommonLogBins') and ws.isCommonLogBins()
        return np.all(np.isclose(difference[:-1], difference[0])) and not commonLogBins
    except IndexError:
        return False


@manage_workspace_names
def pcolormesh(workspaces, fig=None):
    """
    Create a figure containing pcolor subplots

    :param workspaces: A list of workspace handles
    :param fig: An optional figure to contain the new plots. Its current contents will be cleared
    :returns: The figure containing the plots
    """
    # check inputs
    _validate_pcolormesh_inputs(workspaces)

    # create a subplot of the appropriate number of dimensions
    # extend in number of columns if the number of plottables is not a square number
    workspaces_len = len(workspaces)
    fig, axes, nrows, ncols = _create_subplots(workspaces_len, fig=fig)

    row_idx, col_idx = 0, 0
    for subplot_idx in range(nrows * ncols):
        ax = axes[row_idx][col_idx]
        if subplot_idx < workspaces_len:
            ws = workspaces[subplot_idx]
            pcm = pcolormesh_on_axis(ax, ws)
            if col_idx < ncols - 1:
                col_idx += 1
            else:
                row_idx += 1
                col_idx = 0
        else:
            # nothing here
            ax.axis('off')

    # Adjust locations to ensure the plots don't overlap
    fig.subplots_adjust(wspace=SUBPLOT_WSPACE, hspace=SUBPLOT_HSPACE)
    fig.colorbar(pcm, ax=axes.ravel().tolist(), pad=0.06)
    fig.canvas.set_window_title(figure_title(workspaces, fig.number))
    fig.canvas.draw()
    fig.show()
    return fig


def pcolormesh_on_axis(ax, ws):
    """
    Plot a pcolormesh plot of the given workspace on the given axis
    :param ax: A matplotlib axes instance
    :param ws: A mantid workspace instance
    :return:
    """
    ax.clear()
    ax.set_title(ws.name())
    if use_imshow(ws):
        pcm = ax.imshow(ws, cmap=DEFAULT_CMAP, aspect='auto', origin='lower')
    else:
        pcm = ax.pcolormesh(ws, cmap=DEFAULT_CMAP)
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(45)

    return pcm


# ----------------- Compatability functions ---------------------


def plotSpectrum(workspaces, indices, distribution=None, error_bars=False,
                 type=None, window=None, clearWindow=None,
                 waterfall=False):
    """
    Create a figure with a single subplot and for each workspace/index add a
    line plot to the new axes. show() is called before returning the figure instance

    :param workspaces: Workspace/workspaces to plot as a string, workspace handle, list of strings or list of
    workspaces handles.
    :param indices: A single int or list of ints specifying the workspace indices to plot
    :param distribution: ``None`` (default) asks the workspace. ``False`` means
                         divide by bin width. ``True`` means do not divide by bin width.
                         Applies only when the the workspace is a MatrixWorkspace histogram.
    :param error_bars: If true then error bars will be added for each curve
    :param type: curve style for plot (-1: unspecified; 0: line, default; 1: scatter/dots)
    :param window: Ignored. Here to preserve backwards compatibility
    :param clearWindow: Ignored. Here to preserve backwards compatibility
    :param waterfall:
    """
    if type == 1:
        fmt = 'o'
    else:
        fmt = '-'

    return plot(workspaces, wksp_indices=indices,
                errors=error_bars, fmt=fmt)


# -----------------------------------------------------------------------------
# 'Private' Functions
# -----------------------------------------------------------------------------
def _raise_if_not_sequence(value, seq_name, element_type=None):
    """
    Raise a ValueError if the given object is not a sequence

    :param value: The value object to validate
    :param seq_name: The variable name of the sequence for the error message
    :param element_type: An optional type to provide to check that each element
    is an instance of this type
    :raises ValueError: if the conditions are not met
    """
    accepted_types = (list, tuple, range)
    if type(value) not in accepted_types:
        raise ValueError("{} should be a list or tuple, "
                         "instead found '{}'".format(seq_name,
                                                     value.__class__.__name__))
    if element_type is not None:
        def raise_if_not_type(x):
            if not isinstance(x, element_type):
                raise ValueError("Unexpected type: '{}'".format(x.__class__.__name__))

        # Map in Python3 is an iterator, so ValueError will not be raised unless the values are yielded.
        # converting to a list forces yielding
        list(map(raise_if_not_type, value))


def _validate_plot_inputs(workspaces, spectrum_nums, wksp_indices, tiled=False, overplot=False):
    """Raises a ValueError if any arguments have the incorrect types"""
    if spectrum_nums is not None and wksp_indices is not None:
        raise ValueError("Both spectrum_nums and wksp_indices supplied. "
                         "Please supply only 1.")

    if tiled and overplot:
        raise ValueError("Both tiled and overplot flags set to true. "
                         "Please set only one to true.")

    _raise_if_not_sequence(workspaces, 'workspaces', MatrixWorkspace)

    if spectrum_nums is not None:
        _raise_if_not_sequence(spectrum_nums, 'spectrum_nums')

    if wksp_indices is not None:
        _raise_if_not_sequence(wksp_indices, 'wksp_indices')


def _validate_workspace_names(workspaces):
    """
    Checks if the workspaces passed into a plotting function are workspace names, and
    retrieves the workspaces if they are.
    This function assumes that we do not have a mix of workspaces and workspace names.
    :param workspaces: A list of workspaces or workspace names
    :return: A list of workspaces
    """
    try:
        _raise_if_not_sequence(workspaces, 'workspaces', string_types)
    except ValueError:
        return workspaces
    else:
        return AnalysisDataService.Instance().retrieveWorkspaces(workspaces, unrollGroups=True)


def _validate_pcolormesh_inputs(workspaces):
    """Raises a ValueError if any arguments have the incorrect types"""
    _raise_if_not_sequence(workspaces, 'workspaces', MatrixWorkspace)


def _create_subplots(nplots, fig=None):
    """
    Create a set of subplots suitable for a given number of plots. A stripped down
    version of plt.subplots that can accept an existing figure instance.

    :param nplots: The number of plots required
    :param fig: An optional figure. It is cleared before plotting the new contents
    :return: A 2-tuple of (fig, axes)
    """
    import matplotlib.pyplot as plt
    square_side_len = int(math.ceil(math.sqrt(nplots)))
    nrows, ncols = square_side_len, square_side_len
    if square_side_len * square_side_len != nplots:
        # not a square number - square_side_len x square_side_len
        # will be large enough but we could end up with an empty
        # row so chop that off
        if nplots <= (nrows - 1) * ncols:
            nrows -= 1

    if fig is None:
        fig = plt.figure()
    else:
        fig.clf()
    # annoyling this repl
    nplots = nrows * ncols
    gs = GridSpec(nrows, ncols)
    axes = np.empty(nplots, dtype=object)
    ax0 = fig.add_subplot(gs[0, 0], projection=PROJECTION)
    axes[0] = ax0
    for i in range(1, nplots):
        axes[i] = fig.add_subplot(gs[i // ncols, i % ncols],
                                  projection=PROJECTION)
    axes = axes.reshape(nrows, ncols)

    return fig, axes, nrows, ncols
