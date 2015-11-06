#!/usr/bin/python
#
# CCLib_proxy Utilities
# Copyright (c) 2014 Ioannis Charalampidis
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#  
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

from cclib import CCDebugger, CCHEXFile
import sys

# Wait for filename
if len(sys.argv) < 2:
	print "ERROR: Please specify a filename to dump the FLASH memory to!"
	sys.exit(1)

# Open debugger
try:
	dbg = CCDebugger("/dev/ttyACM0")
except Exception as e:
	print "ERROR: %s" % str(e)
	sys.exit(1)

# Get info
print "\nChip information:"
print "      Chip ID : 0x%04x" % dbg.chipID
print "   Flash size : %i Kb" % dbg.chipInfo['flash']
print "    SRAM size : %i Kb" % dbg.chipInfo['sram']
if dbg.chipInfo['usb']:
	print "          USB : Yes"
else:
	print "          USB : No"

# Get serial number
print "\nReading %i KBytes to %s..." % (dbg.chipInfo['flash'], sys.argv[1])
hexFile = CCHEXFile(sys.argv[1])

#enter debug mode
dbg.enter()

try:
	maxPages = dbg.chipInfo['flash']
	for p in range(maxPages):
		pageAddress = p*dbg.flashPageSize
		
		print "\r> %3d%%: reading page %d of %d..." % ((((100.0*p)/(maxPages-1))), p, maxPages-1),
		sys.stdout.flush()
		
		readPage = dbg.readFlashPage(pageAddress)
		#for x in readPage:
		#	print "%02X" % (x), 
		#
		hexFile.stack(readPage)
		
	print "> completed. will (re)start target now"
	print ""

	dbg.setPC(0x0000)
	dbg.resume()
	
except Exception as e:
 	print "ERROR: %s" % str(e)
 	sys.exit(3)



# Save file
hexFile.save()

# Done
print "\n\nCompleted"
print ""
