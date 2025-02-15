# Mantid Repository : https://github.com/mantidproject/mantid
#
# Copyright &copy; 2019 ISIS Rutherford Appleton Laboratory UKRI,
#     NScD Oak Ridge National Laboratory, European Spallation Source
#     & Institut Laue - Langevin
# SPDX - License - Identifier: GPL - 3.0 +
#  This file is part of the mantid workbench.
#
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

# system imports
import unittest

# third-party library imports
import matplotlib

matplotlib.use('AGG')  # noqa
import numpy as np
from qtpy.QtCore import Qt
from testhelpers import assert_almost_equal

# local package imports
from mantid.plots import MantidAxes
from mantid.py3compat.mock import MagicMock, PropertyMock, call, patch
from mantid.simpleapi import CreateWorkspace
from mantidqt.plotting.figuretype import FigureType
from mantidqt.plotting.functions import plot
from workbench.plotting.figureinteraction import FigureInteraction


class FigureInteractionTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ws = CreateWorkspace(
            DataX=np.array([10, 20, 30], dtype=np.float64),
            DataY=np.array([2, 3], dtype=np.float64),
            DataE=np.array([0.02, 0.02], dtype=np.float64),
            Distribution=False,
            UnitX='Wavelength',
            YUnitLabel='Counts',
            OutputWorkspace='ws')
        cls.ws1 = CreateWorkspace(
            DataX=np.array([11, 21, 31], dtype=np.float64),
            DataY=np.array([3, 4], dtype=np.float64),
            DataE=np.array([0.03, 0.03], dtype=np.float64),
            Distribution=False,
            UnitX='Wavelength',
            YUnitLabel='Counts',
            OutputWorkspace='ws1')

    @classmethod
    def tearDownClass(cls):
        cls.ws.delete()
        cls.ws1.delete()

    def setUp(self):
        fig_manager = self._create_mock_fig_manager_to_accept_right_click()
        fig_manager.fit_browser.tool = None
        self.interactor = FigureInteraction(fig_manager)

    # Success tests
    def test_construction_registers_handler_for_button_press_event(self):
        fig_manager = MagicMock()
        fig_manager.canvas = MagicMock()
        interactor = FigureInteraction(fig_manager)
        expected_call = [
            call('button_press_event', interactor.on_mouse_button_press),
            call('button_release_event', interactor.on_mouse_button_release),
            call('draw_event', interactor.draw_callback),
            call('motion_notify_event', interactor.motion_event),
            call('resize_event', interactor.mpl_redraw_annotations),
            call('figure_leave_event', interactor.on_leave),
            call('axis_leave_event', interactor.on_leave),
        ]
        fig_manager.canvas.mpl_connect.assert_has_calls(expected_call)
        self.assertEqual(len(expected_call), fig_manager.canvas.mpl_connect.call_count)

    def test_disconnect_called_for_each_registered_handler(self):
        fig_manager = MagicMock()
        canvas = MagicMock()
        fig_manager.canvas = canvas
        interactor = FigureInteraction(fig_manager)
        interactor.disconnect()
        self.assertEqual(interactor.nevents, canvas.mpl_disconnect.call_count)

    @patch('workbench.plotting.figureinteraction.QMenu',
           autospec=True)
    @patch('workbench.plotting.figureinteraction.figure_type',
           autospec=True)
    def test_right_click_gives_no_context_menu_for_empty_figure(self, mocked_figure_type,
                                                                mocked_qmenu):
        fig_manager = self._create_mock_fig_manager_to_accept_right_click()
        interactor = FigureInteraction(fig_manager)
        mouse_event = self._create_mock_right_click()
        mocked_figure_type.return_value = FigureType.Empty

        with patch.object(interactor.toolbar_manager, 'is_tool_active',
                          lambda: False):
            interactor.on_mouse_button_press(mouse_event)
            self.assertEqual(0, mocked_qmenu.call_count)

    @patch('workbench.plotting.figureinteraction.QMenu',
           autospec=True)
    @patch('workbench.plotting.figureinteraction.figure_type',
           autospec=True)
    def test_right_click_gives_no_context_menu_for_color_plot(self, mocked_figure_type,
                                                              mocked_qmenu):
        fig_manager = self._create_mock_fig_manager_to_accept_right_click()
        interactor = FigureInteraction(fig_manager)
        mouse_event = self._create_mock_right_click()
        mocked_figure_type.return_value = FigureType.Image

        with patch.object(interactor.toolbar_manager, 'is_tool_active',
                          lambda: False):
            interactor.on_mouse_button_press(mouse_event)
            self.assertEqual(0, mocked_qmenu.call_count)

    @patch('workbench.plotting.figureinteraction.QMenu',
           autospec=True)
    @patch('workbench.plotting.figureinteraction.figure_type',
           autospec=True)
    def test_right_click_gives_context_menu_for_plot_without_fit_enabled(self, mocked_figure_type,
                                                                         mocked_qmenu_cls):
        fig_manager = self._create_mock_fig_manager_to_accept_right_click()
        fig_manager.fit_browser.tool = None
        interactor = FigureInteraction(fig_manager)
        mouse_event = self._create_mock_right_click()
        mouse_event.inaxes.get_xlim.return_value = (1, 2)
        mouse_event.inaxes.get_ylim.return_value = (1, 2)
        mocked_figure_type.return_value = FigureType.Line

        # Expect a call to QMenu() for the outer menu followed by two more calls
        # for the Axes and Normalization menus
        qmenu_call1 = MagicMock()
        qmenu_call2 = MagicMock()
        qmenu_call3 = MagicMock()
        qmenu_call4 = MagicMock()
        mocked_qmenu_cls.side_effect = [qmenu_call1, qmenu_call2, qmenu_call3, qmenu_call4]

        with patch('workbench.plotting.figureinteraction.QActionGroup',
                   autospec=True):
            with patch.object(interactor.toolbar_manager, 'is_tool_active',
                              lambda: False):
                with patch.object(interactor.errors_manager, 'add_error_bars_menu', MagicMock()):
                    interactor.on_mouse_button_press(mouse_event)
                    self.assertEqual(0, qmenu_call1.addSeparator.call_count)
                    self.assertEqual(0, qmenu_call1.addAction.call_count)
                    expected_qmenu_calls = [call(),
                                            call("Axes", qmenu_call1),
                                            call("Normalization", qmenu_call1),
                                            call("Markers", qmenu_call1)]
                    self.assertEqual(expected_qmenu_calls, mocked_qmenu_cls.call_args_list)
                    # 4 actions in Axes submenu
                    self.assertEqual(4, qmenu_call2.addAction.call_count)
                    # 2 actions in Normalization submenu
                    self.assertEqual(2, qmenu_call3.addAction.call_count)
                    # 3 actions in Markers submenu
                    self.assertEqual(3, qmenu_call4.addAction.call_count)

    def test_toggle_normalization_no_errorbars(self):
        self._test_toggle_normalization(errorbars_on=False, plot_kwargs={'distribution': True})

    def test_toggle_normalization_with_errorbars(self):
        self._test_toggle_normalization(errorbars_on=True, plot_kwargs={'distribution': True})

    def test_correct_yunit_label_when_overplotting_after_normaliztion_toggle(self):
        fig = plot([self.ws], spectrum_nums=[1], errors=True,
                   plot_kwargs={'distribution': True})
        mock_canvas = MagicMock(figure=fig)
        fig_manager_mock = MagicMock(canvas=mock_canvas)
        fig_interactor = FigureInteraction(fig_manager_mock)

        ax = fig.axes[0]
        fig_interactor._toggle_normalization(ax)
        self.assertEqual("Counts ($\AA$)$^{-1}$", ax.get_ylabel())
        plot([self.ws1], spectrum_nums=[1], errors=True, overplot=True, fig=fig)
        self.assertEqual("Counts ($\AA$)$^{-1}$", ax.get_ylabel())

    def test_normalization_toggle_with_no_autoscale_on_update_no_errors(self):
        self._test_toggle_normalization(errorbars_on=False,
                                        plot_kwargs={'distribution': True, 'autoscale_on_update': False})

    def test_normalization_toggle_with_no_autoscale_on_update_with_errors(self):
        self._test_toggle_normalization(errorbars_on=True,
                                        plot_kwargs={'distribution': True, 'autoscale_on_update': False})

    # Failure tests
    def test_construction_with_non_qt_canvas_raises_exception(self):
        class NotQtCanvas(object):
            pass

        class FigureManager(object):
            def __init__(self):
                self.canvas = NotQtCanvas()

        self.assertRaises(RuntimeError, FigureInteraction, FigureManager())

    def test_context_menu_change_axis_scale_is_axis_aware(self):
        fig = plot([self.ws, self.ws1], spectrum_nums=[1, 1], tiled=True)
        mock_canvas = MagicMock(figure=fig)
        fig_manager_mock = MagicMock(canvas=mock_canvas)
        fig_interactor = FigureInteraction(fig_manager_mock)
        scale_types = ("log", "log")

        ax = fig.axes[0]
        ax1 = fig.axes[1]
        current_scale_types = (ax.get_xscale(), ax.get_yscale())
        current_scale_types1 = (ax1.get_xscale(), ax1.get_yscale())
        self.assertEqual(current_scale_types, current_scale_types1)

        fig_interactor._quick_change_axes(scale_types, ax)
        current_scale_types2 = (ax.get_xscale(), ax.get_yscale())
        self.assertNotEqual(current_scale_types2, current_scale_types1)

    # Private methods
    def _create_mock_fig_manager_to_accept_right_click(self):
        fig_manager = MagicMock()
        canvas = MagicMock()
        type(canvas).buttond = PropertyMock(return_value={Qt.RightButton: 3})
        fig_manager.canvas = canvas
        return fig_manager

    def _create_mock_right_click(self):
        mouse_event = MagicMock(inaxes=MagicMock(spec=MantidAxes))
        type(mouse_event).button = PropertyMock(return_value=3)
        return mouse_event

    def _test_toggle_normalization(self, errorbars_on, plot_kwargs):
        fig = plot([self.ws], spectrum_nums=[1], errors=errorbars_on,
                   plot_kwargs=plot_kwargs)
        mock_canvas = MagicMock(figure=fig)
        fig_manager_mock = MagicMock(canvas=mock_canvas)
        fig_interactor = FigureInteraction(fig_manager_mock)

        # Earlier versions of matplotlib do not store the data assciated with a
        # line with high precision and hence we need to set a lower tolerance
        # when making comparisons of this data
        if matplotlib.__version__ < "2":
            decimal_tol = 1
        else:
            decimal_tol = 7

        ax = fig.axes[0]
        fig_interactor._toggle_normalization(ax)
        assert_almost_equal(ax.lines[0].get_xdata(), [15, 25])
        assert_almost_equal(ax.lines[0].get_ydata(), [0.2, 0.3], decimal=decimal_tol)
        self.assertEqual("Counts ($\\AA$)$^{-1}$", ax.get_ylabel())
        fig_interactor._toggle_normalization(ax)
        assert_almost_equal(ax.lines[0].get_xdata(), [15, 25])
        assert_almost_equal(ax.lines[0].get_ydata(), [2, 3], decimal=decimal_tol)
        self.assertEqual("Counts", ax.get_ylabel())

    @patch('workbench.plotting.figureinteraction.QMenu', autospec=True)
    @patch('workbench.plotting.figureinteraction.figure_type', autospec=True)
    def test_right_click_gives_marker_menu_when_hovering_over_one(self, mocked_figure_type, mocked_qmenu_cls):
        mouse_event = self._create_mock_right_click()
        mouse_event.inaxes.get_xlim.return_value = (1, 2)
        mouse_event.inaxes.get_ylim.return_value = (1, 2)
        mocked_figure_type.return_value = FigureType.Line
        marker1 = MagicMock()
        marker2 = MagicMock()
        marker3 = MagicMock()
        self.interactor.markers = [marker1, marker2, marker3]
        for marker in self.interactor.markers:
            marker.is_above.return_value = True

        # Expect a call to QMenu() for the outer menu followed by two more calls
        # for the Axes and Normalization menus
        qmenu_call1 = MagicMock()
        qmenu_call2 = MagicMock()
        qmenu_call3 = MagicMock()
        qmenu_call4 = MagicMock()
        mocked_qmenu_cls.side_effect = [qmenu_call1, qmenu_call2, qmenu_call3, qmenu_call4]

        with patch('workbench.plotting.figureinteraction.QActionGroup', autospec=True):
            with patch.object(self.interactor.toolbar_manager, 'is_tool_active', lambda: False):
                with patch.object(self.interactor.errors_manager, 'add_error_bars_menu', MagicMock()):
                    self.interactor.on_mouse_button_press(mouse_event)
                    self.assertEqual(0, qmenu_call1.addSeparator.call_count)
                    self.assertEqual(0, qmenu_call1.addAction.call_count)
                    expected_qmenu_calls = [call(),
                                            call(marker1.name, qmenu_call1),
                                            call(marker2.name, qmenu_call1),
                                            call(marker3.name, qmenu_call1)]
                    self.assertEqual(expected_qmenu_calls, mocked_qmenu_cls.call_args_list)
                    # 2 Actions in marker menu
                    self.assertEqual(2, qmenu_call2.addAction.call_count)
                    self.assertEqual(2, qmenu_call3.addAction.call_count)
                    self.assertEqual(2, qmenu_call4.addAction.call_count)

    @patch('workbench.plotting.figureinteraction.SingleMarker')
    def test_adding_horizontal_marker_adds_correct_marker(self, mock_marker):
        y0, y1 = 0, 1
        data = MagicMock()
        axis = MagicMock()
        self.interactor._add_horizontal_marker(data, y0, y1, axis)
        expected_call = call(self.interactor.canvas, '#2ca02c', data, y0, y1,
                             name='marker 0',
                             marker_type='YSingle',
                             line_style='dashed',
                             axis=axis)

        self.assertEqual(1, mock_marker.call_count)
        mock_marker.assert_has_calls([expected_call])

    @patch('workbench.plotting.figureinteraction.SingleMarker')
    def test_adding_vertical_marker_adds_correct_marker(self, mock_marker):
        x0, x1 = 0, 1
        data = MagicMock()
        axis = MagicMock()
        self.interactor._add_vertical_marker(data, x0, x1, axis)
        expected_call = call(self.interactor.canvas, '#2ca02c', data, x0, x1,
                             name='marker 0',
                             marker_type='XSingle',
                             line_style='dashed',
                             axis=axis)

        self.assertEqual(1, mock_marker.call_count)
        mock_marker.assert_has_calls([expected_call])

    def test_delete_marker_does_not_delete_markers_if_not_present(self):
        marker = MagicMock()
        self.interactor.markers = []

        self.interactor._delete_marker(marker)

        self.assertEqual(0, self.interactor.canvas.draw.call_count)
        self.assertEqual(0, marker.marker.remove.call_count)
        self.assertEqual(0, marker.remove_all_annotations.call_count)

    def test_delete_marker_preforms_correct_cleanup(self):
        marker = MagicMock()
        self.interactor.markers = [marker]

        self.interactor._delete_marker(marker)

        self.assertEqual(1, marker.marker.remove.call_count)
        self.assertEqual(1, marker.remove_all_annotations.call_count)
        self.assertEqual(1, self.interactor.canvas.draw.call_count)
        self.assertNotIn(marker, self.interactor.markers)

    @patch('workbench.plotting.figureinteraction.SingleMarkerEditor')
    @patch('workbench.plotting.figureinteraction.QApplication')
    def test_edit_marker_opens_correct_editor(self, mock_qapp, mock_editor):
        marker = MagicMock()
        expected_call = [call(self.interactor.canvas,
                              marker,
                              self.interactor.valid_lines,
                              self.interactor.valid_colors,
                              [])]

        self.interactor._edit_marker(marker)

        self.assertEqual(1, mock_qapp.restoreOverrideCursor.call_count)
        mock_editor.assert_has_calls(expected_call)

    @patch('workbench.plotting.figureinteraction.GlobalMarkerEditor')
    def test_global_edit_marker_opens_correct_editor(self, mock_editor):
        marker = MagicMock()
        self.interactor.markers = [marker]
        expected_call = [call(self.interactor.canvas, [marker],
                              self.interactor.valid_lines,
                              self.interactor.valid_colors)]

        self.interactor._global_edit_markers()

        mock_editor.assert_has_calls(expected_call)

    def test_motion_event_returns_if_toolbar_has_active_tools(self):
        self.interactor.toolbar_manager.is_tool_active = MagicMock(return_value=True)
        self.interactor._set_hover_cursor = MagicMock()
        self.interactor.motion_event(MagicMock())

        self.assertEqual(0, self.interactor._set_hover_cursor.call_count)

    def test_motion_event_changes_cursor_and_draws_canvas_if_any_marker_is_moving(self):
        markers = [MagicMock(), MagicMock(), MagicMock()]
        for marker in markers:
            marker.mouse_move.return_value = True
        event = MagicMock()
        event.xdata = 1
        event.ydata = 2
        self.interactor.markers = markers
        self.interactor.toolbar_manager.is_tool_active = MagicMock(return_value=False)
        self.interactor._set_hover_cursor = MagicMock()

        self.interactor.motion_event(event)

        self.interactor._set_hover_cursor.assert_has_calls([call(1, 2)])
        self.assertEqual(1, self.interactor.canvas.draw.call_count)

    def test_motion_event_changes_cursor_and_does_not_draw_canvas_if_no_marker_is_moving(self):
        markers = [MagicMock(), MagicMock(), MagicMock()]
        for marker in markers:
            marker.mouse_move.return_value = False
        event = MagicMock()
        event.xdata = 1
        event.ydata = 2
        self.interactor.markers = markers
        self.interactor.toolbar_manager.is_tool_active = MagicMock(return_value=False)
        self.interactor._set_hover_cursor = MagicMock()

        self.interactor.motion_event(event)

        self.interactor._set_hover_cursor.assert_has_calls([call(1, 2)])
        self.assertEqual(0, self.interactor.canvas.draw.call_count)

    def test_redraw_annotations_removes_and_adds_all_annotations_for_all_markers(self):
        markers = [MagicMock(), MagicMock(), MagicMock()]
        call_list = [call.remove_all_annotations(), call.add_all_annotations()]
        self.interactor.markers = markers
        self.interactor.redraw_annotations()

        for marker in markers:
            marker.assert_has_calls(call_list)

    def test_mpl_redraw_annotations_does_not_redraw_if_event_does_not_have_a_button_attribute(self):
        self.interactor.redraw_annotations = MagicMock()
        event = MagicMock(spec='no_button')
        event.no_button = MagicMock(spec='no_button')

        self.interactor.mpl_redraw_annotations(event.no_button)
        self.assertEqual(0, self.interactor.redraw_annotations.call_count)

    def test_mpl_redraw_annotations_does_not_redraw_if_event_button_not_pressed(self):
        self.interactor.redraw_annotations = MagicMock()
        event = MagicMock()
        event.button = None
        self.interactor.mpl_redraw_annotations(event)
        self.assertEqual(0, self.interactor.redraw_annotations.call_count)

    def test_mpl_redraw_annotations_redraws_if_button_pressed(self):
        self.interactor.redraw_annotations = MagicMock()
        event = MagicMock()
        self.interactor.mpl_redraw_annotations(event)
        self.assertEqual(1, self.interactor.redraw_annotations.call_count)


if __name__ == '__main__':
    unittest.main()
