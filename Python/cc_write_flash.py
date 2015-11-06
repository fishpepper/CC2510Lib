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
import time
import getopt

def usage():
	print "usage: cc_write_flash.py [-e] [-d] <hex file> "
	print ""
	print "       -e          optional argument, forces a full chip erase"
	print "       -d          optional argument, tty to use (default is /dev/ttyACM0)"
	print "       <hex file>  hex file to write"
	print ""
	

#default is no full chip erase!
full_erase = 0
tty = "/dev/ttyACM0"

if len(sys.argv) < 1:
	usage()
	print "ee"
	sys.exit(2)

try:
	(opts, args) = getopt.getopt(sys.argv[1:], "ed:", ["erase", "device="])
except getopt.GetoptError:          
	usage()                         
	sys.exit(2)                     
for opt, arg in opts:
	if opt in ("-e", "--erase"):
		full_erase = 1
	elif opt in ("-d", "--device"):
		tty = arg

if (len(args) != 1):
	print "ERROR: Please specify a source hex filename!"
	usage()
	sys.exit(2)

#get filename
filename = "".join(args)

#there is no need to do a page erase
#when we do a full erase...
do_page_erase = True
if (full_erase):
	do_page_erase = False


#open debugger
try:
	dbg = CCDebugger(tty)
except Exception as e:
	print "ERROR: %s" % str(e)
	sys.exit(1)

print "> using file " + filename

# Get info
print "> Chip information:"
print "                     Chip ID    : 0x%04x" % dbg.chipID
print "                     Flash size : %3i Kb" % dbg.chipInfo['flash']
print "                    SRAM size   : %3i Kb" % dbg.chipInfo['sram']
print ""

# Parse the HEX file
hexFile = CCHEXFile(filename)
hexFile.load()

# Display sections & calculate max memory usage
maxMem = 0

#build flash image
flash_data = bytearray([0xFF] * dbg.flashSize )

print "> Sections in %s:\n" % filename
print "            Addr.    Size"
print "            -------- -------------"
for mb in hexFile.memBlocks:
	
	# Calculate top position
	memTop = mb.addr + mb.size
	
	#check if no data (all 0xFF)
	empty = bytearray([0xFF] * mb.size)
	if (empty == mb.bytes):
		#no data, ignore this
		print "            0x%04x     %6i B [EMPTY, IGNORED!]" % (mb.addr, mb.size)
		continue
	else:
		# Print portion
		print "            0x%04x     %6i B " % (mb.addr, mb.size)
		#count size 
		if memTop > maxMem:
			maxMem = memTop
	
	#add to flash image:
	for i in range(mb.size):
		dest = mb.addr + i
		data = mb.bytes[i]
		
		#make sure we have no overlapping writes:
		if (flash_data[dest] != 0xFF):
			print "\nERROR: sections in hex file overlap ?!"
			sys.exit(4)
		else:
			#fine, store this byte
			flash_data[dest] = data
	
	
print "> flash usage: %3.1f%% (%d bytes of %d)" % ((maxMem*100.0/dbg.flashSize),maxMem, dbg.flashSize)

# Check for oversize data
if maxMem > (dbg.flashSize):
	print "ERROR: Data too bit to fit in chip's memory!"
	sys.exit(4)


print "> flashing:"
try:
	#enter debug mode
	dbg.enter(); 
	
	if (full_erase):
		"> %3d%%: erasing chip..." % (100*(1.0/17)),
		dbg.chipErase()
		time.sleep(1)
		print "done"
	
	
	maxPages  = dbg.flashSize/dbg.flashPageSize
	emptyPage = bytearray([0xFF] * dbg.flashPageSize)
	
	for p in range(maxPages):
		pageAddress = p*dbg.flashPageSize
		
		#data to write
		pageData = flash_data[pageAddress:(p+1)*dbg.flashPageSize]
		
		#check if page to write is empty:
		if (emptyPage == pageData):
			print "> %3d%%: skipping empty page %d (0xFF) page" % ((100*((2.0+p)/17)), p)
		else:
			print "> %3d%%: writing page %d of %d..." % ((100*((2.0+p)/17)), p, maxPages-1),
			sys.stdout.flush()
			dbg.writeFlashPage(pageAddress, pageData, do_page_erase)
			#read back & verify
			readPage = dbg.readFlashPage(pageAddress)
			#verify:
			if (readPage == pageData):
				print "verify=ok!"
			else:
				print "\nERROR: verification failed!"
				sys.exit(2)
	print "> completed. will start target now"
	print ""

	dbg.setPC(0x0000)
	dbg.resume()
	
except Exception as e:
 	print "ERROR: %s" % str(e)
 	sys.exit(3)
