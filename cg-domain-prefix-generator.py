#!/usr/bin/env python
PROGRAM_NAME = "cg-domain-prefix-generator.py"
PROGRAM_DESCRIPTION = """
CloudGenix script
---------------------------------------

This script indiscriminately adds Routing Prefix filters of the name: "AUTO_DOMAIN_[domain-name] to all of your 
HUB sites. The Prefix filters contain all Global Prefixes of your sites which are members of their respective
domains.

Notes:
As Routing Prefix filters may not have Spaces " " or Question Marks "?" in the name, these will automatically
be replaced with Underscores "_".

If the prefix filter name already exists, the contents of the filter will be completely replace with the 
newly resolved global prefixes. Thus customizations are not currently possible to the prefix filter.


"""

####Library Imports
from cloudgenix import API, jd
import os
import sys
import argparse


def parse_arguments():
    CLIARGS = {}
    parser = argparse.ArgumentParser(
        prog=PROGRAM_NAME,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=PROGRAM_DESCRIPTION
            )
    parser.add_argument('--token', '-t', metavar='"MYTOKEN"', type=str, 
                    help='specify an authtoken to use for CloudGenix authentication')
    parser.add_argument('--authtokenfile', '-f', metavar='"MYTOKENFILE.TXT"', type=str, 
                    help='a file containing the authtoken')
    args = parser.parse_args()
    CLIARGS.update(vars(args))
    return CLIARGS

def authenticate(CLIARGS):
    print("AUTHENTICATING...")
    user_email = None
    user_password = None
    
    sdk = API()    
    ##First attempt to use an AuthTOKEN if defined
    if CLIARGS['token']:                    #Check if AuthToken is in the CLI ARG
        CLOUDGENIX_AUTH_TOKEN = CLIARGS['token']
        print("    ","Authenticating using Auth-Token in from CLI ARGS")
    elif CLIARGS['authtokenfile']:          #Next: Check if an AuthToken file is used
        tokenfile = open(CLIARGS['authtokenfile'])
        CLOUDGENIX_AUTH_TOKEN = tokenfile.read().strip()
        print("    ","Authenticating using Auth-token from file",CLIARGS['authtokenfile'])
    elif "X_AUTH_TOKEN" in os.environ:              #Next: Check if an AuthToken is defined in the OS as X_AUTH_TOKEN
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('X_AUTH_TOKEN')
        print("    ","Authenticating using environment variable X_AUTH_TOKEN")
    elif "AUTH_TOKEN" in os.environ:                #Next: Check if an AuthToken is defined in the OS as AUTH_TOKEN
        CLOUDGENIX_AUTH_TOKEN = os.environ.get('AUTH_TOKEN')
        print("    ","Authenticating using environment variable AUTH_TOKEN")
    else:                                           #Next: If we are not using an AUTH TOKEN, set it to NULL        
        CLOUDGENIX_AUTH_TOKEN = None
        print("    ","Authenticating using interactive login")
    ##ATTEMPT AUTHENTICATION
    if CLOUDGENIX_AUTH_TOKEN:
        sdk.interactive.use_token(CLOUDGENIX_AUTH_TOKEN)
        if sdk.tenant_id is None:
            print("    ","ERROR: AUTH_TOKEN login failure, please check token.")
            sys.exit()
    else:
        while sdk.tenant_id is None:
            sdk.interactive.login(user_email, user_password)
            # clear after one failed login, force relogin.
            if not sdk.tenant_id:
                user_email = None
                user_password = None            
    print("    ","SUCCESS: Authentication Complete")
    return sdk

def logout(sdk):
    print("Logging out")
    sdk.get.logout()


##########MAIN FUNCTION#############
def go(sdk, CLIARGS):

    ###Get list of service binding maps
    result_service = sdk.get.servicebindingmaps()
    if result_service.cgx_status is not True:
        sys.exit("API Error")
    
    result_sites = sdk.get.sites()
    if result_sites.cgx_status is not True:
        sys.exit("API Error")
    
    result_elements = sdk.get.elements()
    if result_elements.cgx_status is not True:
        sys.exit("API Error")

    site_list = result_sites.cgx_content.get("items")
    service_list = result_service.cgx_content.get("items")
    element_list = result_elements.cgx_content.get("items")

    ip_prefix_dict = {}
    for service in service_list:
        prefix_name = str("AUTO_DOMAIN_" + service['name']).replace(" ","_").replace("?","_")
        service_binding =  service['id']
        ip_prefix_dict[service_binding] = {}
        ip_prefix_dict[service_binding]['prefixes'] = []
        ip_prefix_dict[service_binding]['prefix_name'] = prefix_name
        print("============",prefix_name,"============")
        for site in site_list:
            if site['service_binding'] == service['id']:
                result_prefix = sdk.get.localprefixset(site['id'])
                if result_prefix.cgx_content:
                    site_prefixes = result_prefix.cgx_content.get("configured",{}).get("local_prefix_set",{}).get("local_networks",{})
                    for prefix in site_prefixes:
                        for ip_prefix in prefix.get("prefix_set",[]):
                            if ip_prefix.get("ipv4_prefix"):
                                print(str(site['name']) +": "  + str(ip_prefix.get("ipv4_prefix")))
                                ip_prefix_dict[service_binding]['prefixes'].append(str(ip_prefix.get("ipv4_prefix")))
    print("")
    print("")
    ###Get DC's
    dc_site_list = []
    for site in site_list:
        if site['element_cluster_role'] == "HUB":
            dc_site_list.append(site)

    ###Add all Prefixes for All Service bindings to all sites
    for dc_site in dc_site_list:
        for element in element_list:
            if element['site_id'] == dc_site['id']:
                for service_binding in ip_prefix_dict.keys():
                    print("============ Adding Routing Prefix",ip_prefix_dict[service_binding]['prefix_name'],"to site",site['name'],"element",element['name'],"============")
                    add_prefix_to_site(dc_site, element, ip_prefix_dict, sdk, service_binding)
                print("")

def add_prefix_to_site( site, element, ip_prefix_dict, sdk, service_binding):
    ###does Prefix Exist?
    if service_binding not in ip_prefix_dict.keys():
        return False
    
    result_routing_prefixlists = sdk.get.routing_prefixlists(site['id'], element['id'])
    if result_routing_prefixlists.cgx_status is not True:
        sys.exit("API Error")

    routing_prefix_list = result_routing_prefixlists.cgx_content.get("items")

    prefix_exists = False
    for routing_prefix in routing_prefix_list:
        if routing_prefix['name'] == ip_prefix_dict[service_binding]['prefix_name']:
            print("Existing Prefix Found at site",site['name'], "for element",element['name'])
            prefix_exists = True
            routing_prefix['prefix_filter_list'].clear()

            counter = 0
            for prefix in ip_prefix_dict[service_binding]['prefixes']:
                counter += 10
                routing_prefix['prefix_filter_list'].append( {'order': counter, 'permit': True, 'prefix': prefix, 'ge': 0, 'le': 0} )

            put_result = sdk.put.routing_prefixlists(site['id'], element['id'],routing_prefix['id'],routing_prefix)
            
            if put_result.cgx_status:
                print("Updated Prefix Found at site",site['name'], "for element",element['name'],"SUCCESS")
            else:
                print("FAILED TO UPDATE Prefix Found at site",site['name'], "for element",element['name'])
    
    if prefix_exists == False:
        json_data = {'name': ip_prefix_dict[service_binding]['prefix_name'], 'description': None, 'tags': None, 'auto_generated': False, 'prefix_filter_list': []}
        counter = 0
        for prefix in ip_prefix_dict[service_binding]['prefixes']:
            counter += 10
            json_data['prefix_filter_list'].append( {'order': counter, 'permit': True, 'prefix': prefix, 'ge': 0, 'le': 0} )
        if counter > 0:
            post_result = sdk.post.routing_prefixlists(site['id'], element['id'],json_data)
            if post_result.cgx_status:
                print("Created Prefix Found at site",site['name'], "for element",element['name'],"SUCCESS")
            else:
                print("FAILED TO CREATE Prefix Found at site",site['name'], "for element",element['name'])
        else:
            print("Skipping",ip_prefix_dict[service_binding]['prefix_name'],"As no prefixes exist for this domain")
            
if __name__ == "__main__":
    ###Get the CLI Arguments
    CLIARGS = parse_arguments()
    
    ###Authenticate
    SDK = authenticate(CLIARGS)
    
    ###Run Code
    go(SDK, CLIARGS)

    ###Exit Program
    logout(SDK)
