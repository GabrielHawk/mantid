# Mantid Repository : https://github.com/mantidproject/mantid
#
# Copyright &copy; 2018 ISIS Rutherford Appleton Laboratory UKRI,
#     NScD Oak Ridge National Laboratory, European Spallation Source
#     & Institut Laue - Langevin
# SPDX - License - Identifier: GPL - 3.0 +
from __future__ import (absolute_import, division, print_function)

import mantid.simpleapi as mantid

from isis_powder.routines import absorb_corrections, common
from isis_powder.routines.common_enums import WORKSPACE_UNITS
from isis_powder.routines.run_details import create_run_details_object, get_cal_mapping_dict
from isis_powder.polaris_routines import polaris_advanced_config


def calculate_van_absorb_corrections(ws_to_correct, multiple_scattering, is_vanadium):
    mantid.MaskDetectors(ws_to_correct, SpectraList=list(range(1, 55)))

    absorb_dict = polaris_advanced_config.absorption_correction_params
    sample_details_obj = absorb_corrections.create_vanadium_sample_details_obj(config_dict=absorb_dict)
    ws_to_correct = absorb_corrections.run_cylinder_absorb_corrections(
        ws_to_correct=ws_to_correct, multiple_scattering=multiple_scattering, sample_details_obj=sample_details_obj,
        is_vanadium=is_vanadium)
    return ws_to_correct


def _get_run_numbers_for_key(current_mode_run_numbers, key):
    err_message = "this must be under the relevant Rietveld or PDF mode."
    return common.cal_map_dictionary_key_helper(current_mode_run_numbers, key=key,
                                                append_to_error_message=err_message)


def _get_current_mode_dictionary(run_number_string, inst_settings):
    mapping_dict = get_cal_mapping_dict(run_number_string, inst_settings.cal_mapping_path)
    if inst_settings.mode is None:
        ws = mantid.Load('POLARIS'+run_number_string+'.nxs')
        mode, cropping_vals = _determine_chopper_mode(ws)
        inst_settings.mode = mode
        inst_settings.focused_cropping_values = cropping_vals
        mantid.DeleteWorkspace(ws)
    # Get the current mode "Rietveld" or "PDF" run numbers
    return common.cal_map_dictionary_key_helper(mapping_dict, inst_settings.mode)


def get_run_details(run_number_string, inst_settings, is_vanadium_run):
    mode_run_numbers = _get_current_mode_dictionary(run_number_string, inst_settings)

    # Get empty and vanadium
    err_message = "this must be under the relevant Rietveld or PDF mode."

    empty_runs = common.cal_map_dictionary_key_helper(mode_run_numbers,
                                                      key="empty_run_numbers", append_to_error_message=err_message)
    vanadium_runs = common.cal_map_dictionary_key_helper(mode_run_numbers, key="vanadium_run_numbers",
                                                         append_to_error_message=err_message)

    grouping_file_name = inst_settings.grouping_file_name

    return create_run_details_object(run_number_string=run_number_string, inst_settings=inst_settings,
                                     is_vanadium_run=is_vanadium_run, empty_run_number=empty_runs,
                                     vanadium_string=vanadium_runs, grouping_file_name=grouping_file_name)


def save_unsplined_vanadium(vanadium_ws, output_path):
    converted_workspaces = []

    for ws_index in range(vanadium_ws.getNumberOfEntries()):
        ws = vanadium_ws.getItem(ws_index)
        previous_units = ws.getAxis(0).getUnit().unitID()

        if previous_units != WORKSPACE_UNITS.tof:
            ws = mantid.ConvertUnits(InputWorkspace=ws, Target=WORKSPACE_UNITS.tof)

        ws = mantid.RenameWorkspace(InputWorkspace=ws, OutputWorkspace="van_bank_{}".format(ws_index + 1))
        converted_workspaces.append(ws)

    converted_group = mantid.GroupWorkspaces(",".join(ws.name() for ws in converted_workspaces))
    mantid.SaveNexus(InputWorkspace=converted_group, Filename=output_path, Append=False)
    mantid.DeleteWorkspace(converted_group)


def generate_ts_pdf(run_number, focus_file_path, merge_banks=False):
    focused_ws = _obtain_focused_run(run_number, focus_file_path)
    pdf_output = mantid.ConvertUnits(InputWorkspace=focused_ws.name(), Target="MomentumTransfer")
    if merge_banks:
        raise RuntimeError("Merging banks is currently not supported")
    pdf_output = mantid.PDFFourierTransform(Inputworkspace=pdf_output, InputSofQType="S(Q)", PDFType="G(r)",
                                            Filter=True)
    pdf_output = mantid.RebinToWorkspace(WorkspaceToRebin=pdf_output, WorkspaceToMatch=pdf_output[4],
                                         PreserveEvents=True)
    return pdf_output


def _obtain_focused_run(run_number, focus_file_path):
    """
    Searches for the focused workspace to use (based on user specified run number) in the ADS and then the output
    directory.
    If unsuccessful, a ValueError exception is thrown.
    :param run_number: The run number to search for.
    :param focus_file_path: The expected file path for the focused file.
    :return: The focused workspace.
    """
    # Try the ADS first to avoid undesired loading
    if mantid.mtd.doesExist('%s-Results-TOF-Grp' % run_number):
        focused_ws = mantid.mtd['%s-Results-TOF-Grp' % run_number]
    elif mantid.mtd.doesExist('%s-Results-D-Grp' % run_number):
        focused_ws = mantid.mtd['%s-Results-D-Grp' % run_number]
    else:
        # Check output directory
        print('No loaded focused files found. Searching in output directory...')
        try:
            focused_ws = mantid.LoadNexus(Filename=focus_file_path, OutputWorkspace='focused_ws').OutputWorkspace
        except ValueError:
            raise ValueError("Could not find focused file for run number:%s\n"
                             "Please ensure a focused file has been produced and is located in the output directory."
                             % run_number)
    return focused_ws


def _determine_chopper_mode(ws):
    if ws.getRun().hasProperty('Frequency'):
        frequency = ws.getRun()['Frequency'].lastValue()
        print("No chopper mode provided")
        if frequency == 50:
            print("automatically chose Rietveld")
            return 'Rietveld', polaris_advanced_config.rietveld_focused_cropping_values
        if frequency == 0:
            print("automatically chose PDF")
            return 'PDF', polaris_advanced_config.pdf_focused_cropping_values
    else:
        raise ValueError("Chopper frequency not in log data. Please specify a chopper mode")
