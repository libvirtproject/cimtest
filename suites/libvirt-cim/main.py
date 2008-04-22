#!/usr/bin/python
#
# Copyright 2008 IBM Corp.
#
# Authors:
#    Dan Smith <danms@us.ibm.com>
#    Kaitlin Rupert <karupert@us.ibm.com>
#    Zhengang Li <lizg@cn.ibm.com>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307  USA
#

from optparse import OptionParser
import os
import sys
from pywbem import WBEMConnection
sys.path.append('../../lib')
import TestSuite
import commands
from VirtLib import utils
from VirtLib import groups
from CimTest.ReturnCodes import PASS, SKIP, XFAIL
from CimTest.Globals import platform_sup
sys.path.append('./lib')
from XenKvmLib.classes import get_typed_class

parser = OptionParser()
parser.add_option("-i", "--ip", dest="ip", default="localhost",
                  help="IP address of machine to test (default: localhost)")
parser.add_option("-p", "--port", dest="port", type="int", default=5988,
                  help="CIMOM port (default: 5988)")
parser.add_option("-g", "--group", dest="group",
                  help="Specific test group (default: None)")
parser.add_option("-t", "--test", dest="test",
                  help="Specific test case (default: None).  \
Must specify --group or -g to use this option")
parser.add_option("-c", "--clean-log",  
                  action="store_true", dest="clean",
                  help="Will remove existing log files before test run")
parser.add_option("-v", "--virt", dest="virt", type="choice",
                  choices=platform_sup, default="Xen",
                  help="Virt type, select from 'Xen' & 'KVM' & 'XenFV'(default: Xen). ")
parser.add_option("-d", "--debug-output", action="store_true", dest="debug",
                  help="Duplicate the output to stderr")

TEST_SUITE = 'cimtest'

def set_python_path():
    previous_pypath = os.environ.get('PYTHONPATH')

    new_path = ['./lib', '../../lib']
    # make it abs path    
    new_path = map(os.path.abspath, new_path)

    if previous_pypath:
        new_path.append(previous_pypath)

    os.environ['PYTHONPATH'] = ":".join(new_path)

def remove_old_logs(ogroup):
    if ogroup == None:
        group_list = groups.list_groups(TEST_SUITE)
    else:
        group_list = [ogroup]

    for group in group_list:
        g_path = os.path.join(TEST_SUITE, group)
        cmd = "cd %s rm && rm %s" % (g_path, "vsmtest.log")
        status, output = commands.getstatusoutput(cmd)

    print "Cleaned log files."

def get_version(virt, ip):
    conn = WBEMConnection('http://%s' % ip, 
                          (os.getenv('CIM_USER'), os.getenv('CIM_PASS')),
                          os.getenv('CIM_NS'))
    vsms_cn = get_typed_class(virt, 'VirtualSystemManagementService')
    try:
        inst = conn.EnumerateInstances(vsms_cn)
        revision = inst[0]['Revision']
        changeset = inst[0]['Changeset']
    except Exception:
        return '0', 'Unknown'
    return revision, changeset

def main():
    (options, args) = parser.parse_args()


    if options.test and not options.group:
        parser.print_help()
        return 1

    # HACK: Exporting CIMOM_PORT as an env var, to be able to test things 
    # on Director without having to change a lot of code.
    # This will change soon
    if options.port:
        os.environ['CIMOM_PORT'] = str(options.port)
    #

    testsuite = TestSuite.TestSuite()
   
    set_python_path()

    if options.group and options.test:
        test_list = groups.get_one_test(TEST_SUITE, options.group, options.test)
    elif options.group and not options.test:
        test_list = groups.get_group_test_list(TEST_SUITE, options.group)
    else:
        test_list = groups.list_all_tests(TEST_SUITE)

    if not test_list:
        print "Test %s:%s not found" % (options.group, options.test)
        return 1

    if options.clean:
        remove_old_logs(options.group)

    if options.debug:
        dbg = "-d"
    else:
        dbg = ""

    revision, changeset = get_version(options.virt, options.ip)

    print "Testing " + options.virt + " hypervisor"

    for test in test_list:
        t_path = os.path.join(TEST_SUITE, test['group'])
        os.environ['CIM_TC'] = test['test'] 
        cdto = 'cd %s' % t_path
        env = 'CIM_REV=%s CIM_SET=%s' % (revision, changeset)
        run = 'python %s -i %s -v %s %s' % (test['test'], options.ip, 
                                            options.virt, dbg)
        cmd = cdto + ' && ' + env + ' ' + run
        status, output = commands.getstatusoutput(cmd)

        os_status = os.WEXITSTATUS(status)

        if os_status == PASS:
            testsuite.ok(test['group'], test['test'])
        elif os_status == SKIP:
            testsuite.skip(test['group'], test['test'], output)
        elif os_status == XFAIL:
            testsuite.xfail(test['group'], test['test'], output)
        else:
            testsuite.fail(test['group'], test['test'], output)

    testsuite.finish()

if __name__ == '__main__':
    sys.exit(main())


