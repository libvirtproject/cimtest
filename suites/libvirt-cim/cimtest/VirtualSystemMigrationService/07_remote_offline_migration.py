#!/usr/bin/python
#
# Copyright 2009 IBM Corp.
#
# Authors:
#   Deepti B. Kalakeri <deeptik@linux.vnet.ibm.com> 
#    
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
#
# This testcase is used to verify the offline(other) remote migration.
#
#                                                      Date :  12-03-09
#

import sys
import os
from  socket import gethostname, gethostbyaddr
from XenKvmLib import vxml
from XenKvmLib.xm_virt_util import domain_list, net_list
from CimTest.Globals import logger
from XenKvmLib.const import do_main, default_network_name
from CimTest.ReturnCodes import PASS, FAIL, SKIP
from XenKvmLib.classes import get_typed_class
from XenKvmLib.vsmigrations import local_remote_migrate
from XenKvmLib.common_util import poll_for_state_change, create_netpool_conf,\
                                  destroy_netpool

sup_types = ['KVM', 'Xen']

REQUESTED_STATE = 3

def setup_guest(test_dom, ip, virt):
    virt_xml = vxml.get_class(virt)
    cxml = virt_xml(test_dom)
    ret = cxml.cim_define(ip)
    if not ret:
        logger.error("Error define domain %s", test_dom)
        return FAIL, cxml

    status, dom_cs = poll_for_state_change(ip, virt, test_dom,
                                           REQUESTED_STATE)
    if status != PASS:
        cxml.undefine(test_dom)
        logger.error("'%s' didn't change state as expected" % test_dom)
        return FAIL, cxml

    return PASS, cxml

def cleanup_guest_netpool(virt, cxml, test_dom, t_sysname, s_sysname):
    # Clean the domain on target machine.
    # This is req when migration is successful, also when migration is not
    # completely successful VM might be created on the target machine 
    # and hence need to clean.
    target_list = domain_list(t_sysname, virt)
    if target_list  != None and test_dom in target_list:
        ret_value = cxml.undefine(t_sysname)
        if not ret_value:
            logger.info("Failed to undefine the migrated domain '%s' on '%s'",
                         test_dom, t_sysname)

    # clean the networkpool created on the remote machine
    target_net_list = net_list(t_sysname, virt)
    if target_net_list != None and default_network_name in target_net_list:
        ret_value = destroy_netpool(t_sysname, virt, default_network_name)
        if ret_value != PASS:
            logger.info("Unable to destroy networkpool '%s' on '%s'",
                         default_network_name, t_sysname)

    # Remote Migration not Successful, clean the domain on src machine
    src_list = domain_list(s_sysname, virt)
    if src_list != None and test_dom in src_list:
        ret_value = cxml.undefine(s_sysname)
        if not ret_value:
            logger.info("Failed to undefine the domain '%s' on source '%s'",
                         test_dom, s_sysname)


@do_main(sup_types)
def main():
    options = main.options
    virt = options.virt
    s_sysname = gethostbyaddr(options.ip)[0]
    t_sysname = gethostbyaddr(options.t_url)[0] 
    if options.virt == 'KVM' and (t_sysname == s_sysname or \
       t_sysname in s_sysname):
        logger.info("Libvirt does not support local migratoin for KVM")
        return SKIP

    status = FAIL
    test_dom = 'VM_frm_' + gethostname()

    try:
        status, cxml = setup_guest(test_dom, s_sysname, virt)
        if status != PASS:
            logger.error("Error setting up the guest")
            return status

        # create the networkpool used in the domain to be migrated 
        # on the target machine.
        t_net_list = net_list(t_sysname, virt)
        if t_net_list != None and default_network_name not in t_net_list:
            status, netpool = create_netpool_conf(t_sysname, virt, 
                                                  net_name=default_network_name)
            if status != PASS:
               raise Exception("Unable to create network pool '%s' on '%s'" 
                               % (default_network_name, t_sysname))

        # Migrate the test_dom to t_sysname.
        # Enable remote migration by setting remote_migrate=1
        status = local_remote_migrate(s_sysname, t_sysname, virt,
                                      remote_migrate=1, guest_name=test_dom,
                                      mtype='offline')
    except Exception, details:
        logger.error("Exception details :%s", details)
        status = FAIL

    cleanup_guest_netpool(virt, cxml, test_dom, t_sysname, s_sysname)

    return status

if __name__ == "__main__":
    sys.exit(main())
