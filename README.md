# cg-domain-prefix-generator
A tool to automatically create and add Global Prefixes based on Site and DC Group Domain Membership


This script indiscriminately adds Routing Prefix filters of the name: "AUTO_DOMAIN_[domain-name] to all of your 
HUB sites. The Prefix filters contain all Global Prefixes of your sites which are members of their respective
domains.

Notes:
As Routing Prefix filters may not have Spaces " " or Question Marks "?" in the name, these will automatically
be replaced with Underscores "_".

If the prefix filter name already exists, the contents of the filter will be completely replace with the 
newly resolved global prefixes. Thus customizations are not currently possible to the prefix filter.
