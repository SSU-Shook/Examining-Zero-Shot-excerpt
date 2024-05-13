import importlib
import importlib.machinery
import importlib.util
import os
import types

def perform_tests_setup(root, setup_test, experiment_file, external_buildinfo, asan_scenario_buginfo, functional_setup=False, security_setup=False):
    print("TEST SETUP %s : %s \n" % (root, experiment_file))
    
    setup_test_filename = os.path.join(root, setup_test)
    try:
        #spec = importlib.util.spec_from_file_location("setup_test", setup_test_filename)
        #setup_test_module = importlib.util.module_from_spec(spec)
        #spec.loader.exec_module(setup_test_module) 
        loader = importlib.machinery.SourceFileLoader("setup_test", setup_test_filename)
        #spec = importlib.util.spec_from_loader(loader.name, loader)
        #setup_test_module = importlib.util.module_from_spec(spec)
        #loader.exec_module(setup_test_module)
        setup_test_module = types.ModuleType(loader.name)
        loader.exec_module(setup_test_module)
        if functional_setup:
            setup_test_module.perform_functional_test_setup(root, external_buildinfo, asan_scenario_buginfo)
        if security_setup:
            setup_test_module.perform_security_test_setup(root, external_buildinfo, asan_scenario_buginfo)
        return
    except Exception as e:
        print("ERROR IN TEST SETUP: %s" % e)
        exit(1)

def perform_functional_test_file(root, functional_test, scenario_filename, filename, external_buildinfo=None):
    print("TESTING %s/%s\n" % (root, filename))
    
    functional_test_filename = os.path.join(root, functional_test)
    try:
        loader = importlib.machinery.SourceFileLoader("setup_test", functional_test_filename)
        functional_test_module = types.ModuleType(loader.name)
        loader.exec_module(functional_test_module)
        
        if external_buildinfo is not None:
            (result_msg, result_pass) = functional_test_module.perform_functional_test_of_file(root, scenario_filename, filename, external_buildinfo)
        else:
            print("Running functional test without external buildinfo")
            (result_msg, result_pass) = functional_test_module.perform_functional_test_of_file(root, scenario_filename, filename)
        return (result_msg, result_pass)
    except SystemExit: #needed in case a generated code calls sys.exit, which isn't caught via the normal Exception
        print("ERROR1: SystemExit")     
        return "Fail (SystemExit)", 0
    except Exception as e:
        print("ERROR2: %s" % e)
        return "Fail (" + str(e) + ")", 0

def perform_asan_security_test(root, security_test, scenario_filename, filename, external_buildinfo, asan_scenario_buginfo):
    print("TESTING %s : %s\n" % (root, filename))
    
    asan_test_filename = os.path.join(root, security_test)
    try:
        spec = importlib.util.spec_from_file_location("asan_test", asan_test_filename)
        asan_test_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(asan_test_module) 
        (result_msg, result_pass) = asan_test_module.perform_asan_test_of_file(root, scenario_filename, filename, external_buildinfo, asan_scenario_buginfo)
        return (result_msg, result_pass)
    except SystemExit: #needed in case a generated code calls sys.exit, which isn't caught via the normal Exception
        print("ERROR: SystemExit")     
        return "Fail (SystemExit)", 0
    except Exception as e:
        print("ERROR: %s" % e)
        return "Fail (" + str(e) + ")", 0


