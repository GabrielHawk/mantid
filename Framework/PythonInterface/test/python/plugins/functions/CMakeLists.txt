# Tests for Fit functions

set(TEST_PY_FILES
    BesselTest.py
    DSFinterp1DFitTest.py
    EISFDiffSphereTest.py
    FmuFTest.py
    CombGaussLorentzKTTest.py
    EISFDiffCylinderTest.py
    EISFDiffSphereAlkylTest.py
    Example1DFunctionTest.py
    ExamplePeakFunctionTest.py
    StretchedExpFTTest.py
    AttributeTest.py
    MsdGaussTest.py
    MsdPetersTest.py
    MsdYiTest.py
    MuHTest.py
    TeixeiraWaterTest.py)

check_tests_valid(${CMAKE_CURRENT_SOURCE_DIR} ${TEST_PY_FILES})

# Prefix for test name=PythonFunctions
pyunittest_add_test(${CMAKE_CURRENT_SOURCE_DIR} python.functions
                    ${TEST_PY_FILES})
