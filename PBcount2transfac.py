#! /usr/bin/env python

"""
PBcount2transfac.py convert a table of PB count for each residue
into the transfac format http://meme.sdsc.edu/meme/doc/transfac-format.html

2012 - P. Poulain, A. G. de Brevern 
"""

#===============================================================================
# load modules
#===============================================================================
from optparse import OptionParser
import os
import sys

#===============================================================================
# MAIN - program starts here
#===============================================================================

#-------------------------------------------------------------------------------
# manage parameters
#-------------------------------------------------------------------------------
parser = OptionParser(usage="%prog -f file.PB.count -o output_root_name")
parser.add_option("-f", action="store", type="string", dest="count_name",
help="name of the file that contains PB counts")
parser.add_option("-o", action="store", type="string", dest="out_name",
help="root name for results")

# get all parameters
(options, args) = parser.parse_args()

# check options
if not options.count_name:
    parser.print_help()
    parser.error("option -f is mandatory")

if not options.out_name:
    parser.print_help()
    parser.error("option -o is mandatory")

#-------------------------------------------------------------------------------
# check files
#-------------------------------------------------------------------------------
if options.count_name and not os.path.isfile(options.count_name):
    sys.exit("%s does not appear to be a valid file" % (options.count_name))

#-------------------------------------------------------------------------------
# read count file
#-------------------------------------------------------------------------------
f_in = open(options.count_name, 'r')
count_content = f_in.readlines()
f_in.close()

#-------------------------------------------------------------------------------
# make transfac file
#-------------------------------------------------------------------------------
transfac_content  = "ID %s\n" % options.count_name
transfac_content += "BF unknown\n"
transfac_content += "P0" + count_content[0][2:]
for line in count_content[1:]:
    item = line.split()
    residue = int(item[0])
    transfac_content += "%05d" % residue + line[5:-1] +  "    X" + "\n"
transfac_content += "XX\n"
transfac_content += "//"

#-------------------------------------------------------------------------------
# write transfac file
#-------------------------------------------------------------------------------
transfac_name = options.out_name + '.transfac'
f_out = open(transfac_name, 'w')
f_out.write(transfac_content)
f_out.close()
print "wrote %s" % (transfac_name)
