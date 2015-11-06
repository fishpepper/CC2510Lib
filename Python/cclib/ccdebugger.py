#
# CCLib_proxy Interface Library for High-Level operations
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

from cclib.cchex import toHex, fromHex
import serial
import struct
import math
import time
import sys

# Command constants
CMD_ENTER    = 0x01
CMD_EXIT     = 0x02
CMD_CHIP_ID  = 0x03
CMD_STATUS   = 0x04
CMD_PC       = 0x05
CMD_STEP     = 0x06
CMD_EXEC_1   = 0x07
CMD_EXEC_2   = 0x08
CMD_EXEC_3   = 0x09
CMD_BRUSTWR  = 0x0A
CMD_RD_CFG   = 0x0B
CMD_WR_CFG   = 0x0C
CMD_CHPERASE = 0x0D
CMD_RESUME   = 0x0E
CMD_HALT     = 0x0F
CMD_PING     = 0xF0

# Response constants
ANS_OK       = 0x01
ANS_ERROR    = 0x02
ANS_READY    = 0x03

class CCDebugger:
	"""
	
	CC.Debuger class which uses the CCLib_proxy-compatible arduino firmware.

	Because the CCLib_proxy was used for experimentation with the CCDebugger protocol,
	all the higher-level logic is implemented in this class. In order to cope with the
	performance issues, a binary serial protocol was used.

	The overall flash writing operations are very good, however reading is much slower.

	!!! WARNING !!!

	The higher-level functions are *TAILORED* for CC2540/41 SOC (BLE112,BLE113). 
	DO NOT USE them for ANY other chip!

	"""

	def __init__(self, port):
		"""
		Initialize serial port
		"""
		
		self.show_debug_info = False

		self.debug_active = False

		# Open port
		try:
			self.ser = serial.Serial(port, 115200, timeout=1, rtscts=False)
		except:
			raise IOError("Could not open port %s" % port)

		# Ping
		if self.ping():
			print "Using CCDebugger on port %s" % self.ser.name 
		else:
			raise IOError("Could not find CCLib_proxy device on port %s" % self.ser.name)

		# Get chip info & ID
		self.chipID = self.getChipID()
		self.debugStatus = self.getStatus()
		print self.debugStatus
		self.debugConfig = self.readConfig()

		if (self.chipID & 0xFF00) == 0x8100:
			print "detected a cc2510f16"
			#different on cc2510:
			self.chipInfo = {
				'flash' : 16,
				'usb'   : 0,
				'sram'  : 2
			}
			
			# Populate variables
			self.flashSize = self.chipInfo['flash'] * 1024
			#all cc251x have 0x400 as flash page size
			self.flashPageSize = 0x400
			self.sramSize = self.chipInfo['sram'] * 1024
			self.bulkBlockSize = 0x800 #???
			self.flashWordSize = 2 #cc251x have 2 bytes per word
		else:
			raise IOError("This class works ONLY with CC251xx TI chips (This is a 0x%04x)!" % self.chipID)

	###############################################
	# Low-level functions
	###############################################

	def readFrame(self, raiseException=True):
		"""
		Read and translate the 3-byte response frame from arduino
		"""
		# Read response frame
		status = ord(self.ser.read())
		bH = ord(self.ser.read())
		bL = ord(self.ser.read())

		# Handle error responses
		if status == ANS_ERROR:
			if raiseException:
				raise IOError("CCDebugger responded with an error (0x%02x)" % bL)
			else:
				return -bL

		# Check for responses other than OK
		elif status != ANS_OK:

			# Ready is a special case
			if status == ANS_READY:
				return ANS_READY
			else:
				raise IOError("CCDebugger responded with an unknown status (0x%02x)" % status)

		# Otherwise we are good
		return (bH << 8) | bL

	def sendFrame(self, cmd, c1=0,c2=0,c3=0,raiseException=True ):
		"""
		Send the specified frame to the output queue
		"""
		#print "sending \\x%02X\\x%02X\\x%02X\\x%02X" % ((cmd), (c1), (c2), (c3) )
		# Send the 4-byte command frame
		self.ser.write( chr(cmd)+chr(c1)+chr(c2)+chr(c3) )
		self.ser.flush()

		# Read frame
		return self.readFrame(raiseException)

	###############################################
	# Debug-level functions
	###############################################

	def ping(self):
		"""
		Send a PING frame
		"""

		# This will raise an exception on error
		self.sendFrame(CMD_PING)
		return True


	def enter(self):
		"""
		Enter in debug mode
		"""
		self.debug_active = True
		return self.sendFrame(CMD_ENTER)

	def exit(self):
		"""
		Exit from debug mode by resuming the CPU
		"""
		status = self.sendFrame(CMD_EXIT)
		
		# Update debug status
		self.debugStatus = status
		
		self.debug_active = False
		return status

	def readConfig(self):
		"""
		Read debug configuration
		"""
		return self.sendFrame(CMD_RD_CFG)

	def writeConfig(self, config):
		"""
		Read debug configuration
		"""
		ans = self.sendFrame(CMD_WR_CFG, config)

		# Update local variables
		self.debugConfig = config
		self.debugStatus = ans
		return ans

	def step(self):
		"""
		Step a single instruction
		"""
		return self.sendFrame(CMD_STEP)

	def resume(self):
		"""
		resume program exec
		"""
		return self.sendFrame(CMD_RESUME)
	
	def halt(self):
		"""
		halt program exec
		"""
		return self.sendFrame(CMD_HALT)



	def getChipID(self):
		"""
		Return the ChipID as read from the chip
		"""
		return self.sendFrame(CMD_CHIP_ID)

	def getStatus(self):
		"""
		Return the debug status
		"""
		ans = self.sendFrame(CMD_STATUS)

		# Update local variables
		self.debugStatus = ans
		return ans

	def getPC(self):
		"""
		Return the program counter position
		"""
		return self.sendFrame(CMD_PC)

	def setPC(self, address):
		self.instr(0x02, (address>>8)&0xFF, address&0xFF)

	def instr(self, c1, c2=None, c3=None):
		"""
		Execute a debug instruction
		"""

		# Call the appropriate instruction according
		# to the number of bytes 
		if (c2 == None):
			return self.sendFrame(CMD_EXEC_1, c1)
		elif (c3 == None):
			return self.sendFrame(CMD_EXEC_2, c1, c2)
		else:
			return self.sendFrame(CMD_EXEC_3, c1, c2, c3)

	def instri(self, c1, i1):
		"""
		Execute a debug instruction with 16-bit constant
		"""

		# Split short in high/low order bytes
		cHigh = (i1 >> 8) & 0xFF
		cLow = (i1 & 0xFF)

		# Send instruction
		return self.sendFrame(CMD_EXEC_3, c1, cHigh, cLow)

	def brustWrite(self, data):
		"""
		Perform a brust-write operation which allows us to write
		up to 2Kb in the DBGDATA register.
		"""

		# Validate length
		length = len(data)
		if length > 2048:
			return False

		# Split length in high/low order bytes
		cHigh = (length >> 8) & 0xFF
		cLow = (length & 0xFF)

		# Prepare for BRUST frame transmission
		ans = self.sendFrame(CMD_BRUSTWR, cHigh, cLow)
		if ans != ANS_READY:
			raise IOError("Unable to prepare for brust-write! (Unknown response 0x%02x)" % ans)

		# Start sending data
		for b in data:
			self.ser.write(chr(b & 0xFF))
		self.ser.flush()

		# Handle response & update debug status
		self.debugStatus = self.readFrame()
		return self.debugStatus
	
	def chipErase(self):
		"""
		Perform a chip erase
		"""
		if (not self.debug_active):
			print "ERROR: not in debug mode! did you forget a enter() call?\n"
			sys.exit(2)
			
		# Send chip erase command & update debug status
		self.debugStatus = self.sendFrame(CMD_CHPERASE)

		# Wait until CHIP_ERASE_BUSY goes down
		s = self.getStatus()
		while (( s & 0x80 ) != 0):
			time.sleep(0.01)
			s = self.getStatus()

		# We are good
		self.debugStatus = s
		return self.debugStatus

	###############################################
	# Data reading
	###############################################

	def readXDATA( self, offset, size ):
		"""
		Read any size of buffer from the XDATA region
		"""

		# Setup DPTR
		a = self.instri( 0x90, offset )		# MOV DPTR,#data16

		# Prepare ans array
		ans = bytearray()

		# Read bytes
		for i in range(0, size):
			a = self.instr ( 0xE0 )			# MOVX A,@DPTR
			ans.append(a)
			a = self.instr ( 0xA3 )			# INC DPTR

		# Return ans
		return ans

	def writeXDATA( self, offset, bytes ):
		"""
		Write any size of buffer in the XDATA region
		"""
		
		# Setup DPTR
		a = self.instri( 0x90, offset )		# MOV DPTR,#data16

		# Read bytes
		for b in bytes:
			a = self.instr ( 0x74, b )		# MOV A,#data
			a = self.instr ( 0xF0 )			# MOVX @DPTR,A
			a = self.instr ( 0xA3 )			# INC DPTR

		# Return bytes written
		return len(bytes)

	def readCODE( self, offset, size ):
		"""
		Read any size of buffer from the XDATA+0x8000 (code-mapped) region
		"""

		# Pick the code bank this code chunk belongs to
		fBank = int(offset / 0x8000 )
		self.selectXDATABank( fBank )

		# Recalibrate offset
		offset -= fBank * 0x8000

		# Setup DPTR
		a = self.instri( 0x90, offset )		# MOV DPTR,#data16

		# Prepare ans array
		ans = bytearray()

		# Read bytes
		for i in range(0, size):
			a = self.instr ( 0xE4 )			# MOVX A,@DPTR
			a = self.instr ( 0x93 )			# MOVX A,@DPTR
			ans.append(a)
			a = self.instr ( 0xA3 )			# INC DPTR


		#
		return ans


	def getRegister( self, reg ):
		"""
		Return the value of the given register
		"""
		return self.instr( 0xE5, reg )		# MOV A,direct

	def setRegister( self, reg, v ):
		"""
		Update the value of the 
		"""
		return self.instr( 0x75, reg, v )	# MOV direct,#data

	def selectXDATABank(self, bank):
		"""
		Select XDATA bank from the Memory Arbiter Control register
		"""
		#a = self.getRegister( 0xC7 )
		#a = (a & 0xF8) | (bank & 0x07)
		#return self.setRegister( 0xC7, a )
		return self.instr(0x75, 0xC7, bank*16 + 1);
		

	def selectFlashBank(self, bank):
		"""
		Select a bank for 
		"""
		return self.setRegister( 0x9F, bank & 0x07 )


	###############################################
	# Chip information
	###############################################

	def getSerial(self):
		"""
		Read the IEEE address from the 0x780E register
		"""

		# Serial number is 6 bytes, stored on 0x780E
		bytes = self.readXDATA( 0x780E, 6 )

		# Build serial number string
		serial = ""
		for i in range(5,-1,-1):
			serial += "%02x" % bytes[i]

		# Return serial
		return serial

	def getChipInfo(self):
		"""
		Analyze chip info registers
		"""

		# Get chip info registers
		chipInfo = self.readXDATA(0x6276, 2)

		# Extract the useful info
		return {
			'flash' : pow(2, 4 + ((chipInfo[0] & 0x70) >> 4)), # in Kb
			'usb'	: (chipInfo[0] & 0x08) != 0, # in Kb
			'sram'	: (chipInfo[1] & 0x07) + 1
		}

	def getInfoPage(self):
		"""
		Return the read-only information page (2kb)
		"""

		# Read XDATA
		data = self.readXDATA( 0x7800, self.flashPageSize )

		# Get license key
		return data

	def getLastCODEPage(self):
		"""
		Return the entire last flash page
		"""

		# Return the last page-size bytes
		return self.readCODE( self.flashSize - self.flashPageSize, self.flashPageSize )

	def writeLastCODEPage(self, pageData):
		"""
		Write the entire last flash code page
		"""

		# Validate page data
		if len(pageData) > self.flashPageSize:
			raise IOError("Data bigger than flash page size!")

		# Write flash code page
		return self.writeCODE( self.flashSize - self.flashPageSize, pageData, erase=True )

	###############################################
	# cc251x
	###############################################
	
	def readFlashPage(self, address):
		if (not self.debug_active):
			print "ERROR: not in debug mode! did you forget a enter() call?\n"
			sys.exit(2)
		return self.readCODE(address & 0x7FFFF, self.flashPageSize)
	
	def writeFlashPage(self, address, inputArray, erase_page=True):
		if len(inputArray) != self.flashPageSize:
			raise IOError("input data size != flash page size!")
		
		if (not self.debug_active):
			print "ERROR: not in debug mode! did you forget a enter() call?\n"
			sys.exit(2)

		#calc words per flash page
		words_per_flash_page = self.flashPageSize / self.flashWordSize
		
		#print "words_per_flash_page = %d" % (words_per_flash_page)
		#print "flashWordSize = %d" % (self.flashWordSize)
		if (erase_page): 
			print "[page erased]",
			
		routine8_1 = [
			#see http://www.ti.com/lit/ug/swra124/swra124.pdf page 11
			0x75, 0xAD, ((address >> 8) / self.flashWordSize) & 0x7E, 	#MOV FADDRH, #imm; 
			0x75, 0xAC, 0x00						#MOV FADDRL, #00;
		]
		routine8_erase = [
			0x75, 0xAE, 0x01,						#MOV FLC, #01H; // ERASE 
			#; Wait for flash erase to complete 
			0xE5, 0xAE,							#eraseWaitLoop:  MOV A, FLC; 
			0x20, 0xE7, 0xFB						#JB ACC_BUSY, eraseWaitLoop;
		]
		routine8_2 = [
			#; Initialize the data pointer 
			0x90, 0xF0, 0x00,						#MOV DPTR, #0F000H; 
			#; Outer loops 
			0x7F, (((words_per_flash_page)>>8)&0xFF),			#MOV R7, #imm; 
			0x7E, ((words_per_flash_page)&0xFF),				#MOV R6, #imm; 
			0x75, 0xAE, 0x02,						#MOV FLC, #02H; // WRITE 
			#; Inner loops 
			0x7D, self.flashWordSize,					#writeLoop:          MOV R5, #imm; 
			0xE0,								#writeWordLoop:          MOVX A, @DPTR; 
			0xA3,								#INC DPTR; 
			0xF5, 0xAF,							#MOV FWDATA, A;  
			0xDD, 0xFA,							#DJNZ R5, writeWordLoop; 
			#; Wait for completion 
			0xE5, 0xAE,							#writeWaitLoop:      MOV A, FLC; 
			0x20, 0xE6, 0xFB,						#JB ACC_SWBSY, writeWaitLoop; 
			0xDE, 0xF1,							#DJNZ R6, writeLoop; 
			0xDF, 0xEF,							#DJNZ R7, writeLoop; 
			#set green led for debugging info (DO NOT USE THIS!)
			#LED_GREEN_DIR |= (1<<LED_GREEN_PIN);
			#0x43, 0xFF, 0x18,	#      [24]  935         orl     _P2DIR,#0x10
			#LED_GREEN_PORT = (1<<LED_GREEN_PIN);
			#0x75, 0xA0, 0x18,	#      [24]  937         mov     _P2,#0x10
			#; Done with writing, fake a breakpoint in order to HALT the cpu
			0xA5								#DB 0xA5; 
		]
		
		#build routine 
		routine = routine8_1
		if (erase_page):
			routine += routine8_erase
		routine += routine8_2
		
		#add led code to flash code (for debugging)
		#aroutine = led_routine + routine
		#routine = routine + led_routine
		
		#for x in routine:
		#	print "%02X" % (x),
		
		#halt CPU
		self.halt()
		
		#send data to xdata memory:
		if (self.show_debug_info): print "copying data to xdata"
		self.writeXDATA(0xF000, inputArray)
		
		#send program to xdata mem
		if (self.show_debug_info): print "copying flash routine to xdata"
		self.writeXDATA(0xF000 + self.flashPageSize, routine)
	
		if (self.show_debug_info): print "executing code"
		#execute MOV MEMCTR, (bank * 16) + 1; 
		self.instr(0x75, 0xC7, 0x51)
		
		#set PC to start of program
		self.setPC(0xF000 + self.flashPageSize)
		
		#start program exec, will continue after routine exec due to breakpoint
		self.resume()
		
		
		if (self.show_debug_info): print "page write running",
		
		#set some timeout (2 seconds)
		timeout = 200
		while (timeout > 0):
			#show progress
			if (self.show_debug_info): 
				print ".",
				sys.stdout.flush()
			#check status (bit 0x20 = cpu halted)
			if ((self.getStatus() & 0x20 ) != 0):
				if (self.show_debug_info): print "done"
				break
			#timeout increment
			timeout -= 1
			#delay (10ms)
			time.sleep(0.01)
			
		
		if (timeout <=0):
			raise IOError("flash write timed out!")
		
		self.halt()
		
		if (self.show_debug_info): print "done"


	###############################################
	# BlueGiga-Specific functions
	###############################################

	def mergeBLEInfoPage(self, target, source):
		"""
		Copy the last 64-bytes from source to target
		"""

		# Validate size
		if len(target) != len(source):
			raise IOError("Invalid sizes between target/souce blocks!")

		# Copy upper 64 bytes
		l = len(target)
		target[l-0x40:l] = source[l-0x40:l]

		# Return target
		return target

	def setBLELicense(self, target, license, fromHEX=True):
		"""
		Update the BLE info page and store the given license key
		"""

		# Check if we have to convert the license bytes
		if fromHEX:
			license = fromHex(license)

		# Validate lincense size
		if len(license) != 32:
			raise IOError("Invalid license key size!")

		# Update lincense region
		l = len(target)
		target[l-57:l-25] = license

		# Return target
		return target

	def setBLEAddress(self, target, btAddress, fromHEX=True):
		"""
		Update the BLE info page and store the given license key
		"""

		# Check if we have to convert the bluetooth address bytes
		if fromHEX:
			btAddress = fromHex(btAddress,step=3)

		# Validate lincense size
		if len(btAddress) != 6:
			raise IOError("Invalid bluetooth address size!")

		# Update lincense region
		l = len(target)
		target[l-22:l-16] = btAddress

		# Return target
		return target

	def getBLEInfo(self):
		"""
		Return the translated Bluegiga information struct (last 64 bits)
		"""

		# Get page data
		page = self.readCODE( self.flashSize-0x40, 0x40 )

		# Convert bytes to hex representation
		strLic = "".join( "%02x" % x for x in page[7:39] )
		strBTAddr = "".join( "%02x:" % x for x in page[42:48] )[0:-1]

		# Return translated information
		return {
			"license" : strLic,
			"hwver"   : page[39],
			"btaddr"  : strBTAddr,
			"lockbits": page[48:64]
		}

	def getBLEPStoreSize(self):
		"""
		Return the size (in bytes) of the permanent store
		"""

		# PStore size is stored on 0x1F7EF as page number
		a = self.readCODE(0x1F7EF, 1)

		# Check for invalid values
		if a[0] > int(self.flashSize / self.flashPageSize):
			a[0] = 0

		# Return size in bytes
		return a[0] * self.flashPageSize

	def getBLEPStore(self):
		"""
		Return the permanent store 
		"""
		pass

	def setBLEPSStore(self, storePageData):
		"""
		Update the permanent store
		"""
		pass

	###############################################
	# DMA functions
	###############################################

	def pauseDMA(self, pause):
		"""
		Pause/Unpause DMA in debug mode
		"""
		# Get current debug config
		a = self.readConfig()
		# Update
		if pause:
			a |= 0x4
		else:
			a &= ~0x4
		# Commit
		self.writeConfig(a)

	def configDMAChannel(self, index, srcAddr, dstAddr, trigger, vlen=0, tlen=1, 
		word=False, transferMode=0, srcInc=0, dstInc=0, interrupt=False, m8=True, 
		priority=0, memBase=0x1000):
		"""
		Create a DMA buffer and place it in memory
		"""

		# Calculate numeric flags
		nword = 0
		if word:
			nword = 1
		nirq = 0
		if interrupt:
			nirq = 1
		nm8 = 1
		if m8:
			nm8 = 0

		# Prepare DMA configuration bytes
		config = [
			(srcAddr >> 8) & 0xFF,		# 0: SRCADDR[15:8]
			(srcAddr & 0xFF),			# 1: SRCADDR[7:0]
			(dstAddr >> 8) & 0xFF,		# 2: DESTADDR[15:8]
			(dstAddr & 0xFF),			# 3: DESTADDR[7:0]
			(vlen & 0x07) << 5 |		# 4: VLEN[2:0]
			((tlen >> 8) & 0x1F),		# 4: LEN[12:8]
			(tlen & 0xFF),				# 5: LEN[7:0]
			(nword << 7) |				# 6: WORDSIZE
			(transferMode << 5) |		# 6: TMODE[1:0]
			(trigger & 0x1F),			# 6: TRIG[4:0]
			((srcInc & 0x03) << 6) |	# 7: SRCINC[1:0]
			((dstInc & 0x03) << 4) |	# 7: DESTINC[1:0]
			(nirq << 3) |				# 7: IRQMASK
			(nm8 << 2) |				# 7: M8
			(priority & 0x03)			# 7: PRIORITY[1:0]
		]

		# Pick an offset in memory to store the configuration
		memAddr = memBase + index*8
		self.writeXDATA( memAddr, config )

		# Split address in high/low
		cHigh = (memAddr >> 8) & 0xFF
		cLow = (memAddr & 0xFF)

		# Update DMA registers
		if index == 0:
			self.instr( 0x75, 0xD4, cLow  ) # MOV direct,#data @ DMA0CFGL
			self.instr( 0x75, 0xD5, cHigh ) # MOV direct,#data @ DMA0CFGH

		else:

			# For DMA1+ they reside one after the other, starting
			# on the base address of the first in DMA1CFGH:DMA1CFGL
			memAddr = memBase + 8
			cHigh = (memAddr >> 8) & 0xFF
			cLow = (memAddr & 0xFF)

			self.instr( 0x75, 0xD2, cLow  ) # MOV direct,#data @ DMA1CFGL
			self.instr( 0x75, 0xD3, cHigh ) # MOV direct,#data @ DMA1CFGH

	def getDMAConfig(self, index, memBase=0x1000):
		"""
		Read DMA configuration
		"""
		# Pick an offset in memory to store the configuration
		memAddr = memBase + index*8
		return self.readXDATA(memAddr, 8)

	def setDMASrcAddr(self, index, srcAddr, memBase=0x1000):
		"""
		Set the DMA source address
		"""

		# Pick an offset in memory to store the configuration
		memAddr = memBase + index*8
		self.writeXDATA( memAddr, [
			(srcAddr >> 8) & 0xFF,		# 0: SRCADDR[15:8]
			(srcAddr & 0xFF),			# 1: SRCADDR[7:0]
		])

	def setDMADstAddr(self, index, dstAddr, memBase=0x1000):
		"""
		Set the DMA source address
		"""

		# Pick an offset in memory to store the configuration
		memAddr = memBase + index*8
		self.writeXDATA( memAddr+2, [
			(dstAddr >> 8) & 0xFF,		# 2: DESTADDR[15:8]
			(dstAddr & 0xFF),			# 3: DESTADDR[7:0]
		])

	def armDMAChannel(self, index):
		"""
		Arm a DMA channel (index in 0-4)
		"""

		# Get DMAARM state
		a = self.getRegister(0xD6) # MOV A,direct @ DMAARM

		# Set given flag
		a |= pow(2, index)

		# Update DMAARM state
		self.setRegister(0xD6, a) # MOV direct,#data @ DMAARM

		time.sleep(0.01)

	def disarmDMAChannel(self, index):
		"""
		Disarm a DMA channel (index in 0-4)
		"""

		# Get DMAARM state
		a = self.getRegister( 0xD6 )

		# Unset given flag
		flag = pow(2, index)
		a &= ~flag

		# Update DMAARM state
		self.setRegister( 0xD6, a )

	def isDMAArmed(self, index):
		"""
		Check if DMA IRQ flag is set (index in 0-4)
		"""

		# Get DMAARM state
		a = self.getRegister( 0xD1 )

		# Lookup IRQ bit
		bit = pow(2, index)

		# Check if IRQ bit is set
		return ((a & bit) != 0)

	def isDMAIRQ(self, index):
		"""
		Check if DMA IRQ flag is set (index in 0-4)
		"""

		# Get DMAIRQ state
		a = self.getRegister( 0xD1 )

		# Lookup IRQ bit
		bit = pow(2, index)

		# Check if IRQ bit is set
		return ((a & bit) != 0)

	def clearDMAIRQ(self, index):
		"""
		Clear DMA IRQ flag (index in 0-4)
		"""

		# Get DMAIRQ state
		a = self.getRegister( 0xD1 )

		# Unset given flag
		flag = pow(2, index)
		a &= ~flag

		# Update DMAIRQ state
		self.setRegister( 0xD1, a )

	###############################################
	# Flash functions
	###############################################

	def setFlashWordOffset(self, address):
		"""
		Set the flash address offset in FADDRH:FADDRL
		"""

		# Split address in high/low order bytes
		cHigh = (address >> 8) & 0xFF
		cLow = (address & 0xFF)

		# Place in FADDRH:FADDRL
		self.writeXDATA( 0x6271, [cLow, cHigh])

	def isFlashFull(self):
		"""
		Check if the FULL bit is set in the flash register
		"""

		# Read flash status register
		a = self.readXDATA(0x6270, 1)
		return (a[0] & 0x40 != 0)

	def isFlashBusy(self):
		"""
		Check if the BUSY bit is set in the flash register
		"""

		# Read flash status register
		a = self.readXDATA(0x6270, 1)
		return (a[0] & 0x80 != 0)

	def isFlashAbort(self):
		"""
		Check if the ABORT bit is set in the flash register
		"""

		# Read flash status register
		a = self.readXDATA(0x6270, 1)
		return (a[0] & 0x20 != 0)

	def clearFlashStatus(self):
		"""
		Clear the flash status register
		"""

		# Read & mask-out status register bits
		a = self.readXDATA(0x6270, 1)
		a[0] &= 0x1F
		return self.writeXDATA(0x6270, a)

	def setFlashWrite(self):
		"""
		Set the WRITE bit in the flash control register
		"""

		# Set flash WRITE bit
		a = self.readXDATA(0x6270, 1)
		a[0] |= 0x02
		return self.writeXDATA(0x6270, a)

	def setFlashErase(self):
		"""
		Set the ERASE bit in the flash control register
		"""

		# Set flash ERASE bit
		a = self.readXDATA(0x6270, 1)
		a[0] |= 0x01
		return self.writeXDATA(0x6270, a)

	def writeCODE(self, offset, data, erase=False, verify=False, showProgress=False):
		"""
		Fully automated function for writing the Flash memory.

		WARNING: This requires DMA operations to be unpaused ( use: self.pauseDMA(False) )
		"""

		# Prepare DMA-0 for DEBUG -> RAM (using DBG_BW trigger)
		self.configDMAChannel( 0, 0x6260, 0x0000, 0x1F, tlen=self.bulkBlockSize, srcInc=0, dstInc=1, priority=1, interrupt=True )
		# Prepare DMA-1 for RAM -> FLASH (using the FLASH trigger)
		self.configDMAChannel( 1, 0x0000, 0x6273, 0x12, tlen=self.bulkBlockSize, srcInc=1, dstInc=0, priority=2, interrupt=True )

		# Reset flags
		self.clearFlashStatus()
		self.clearDMAIRQ(0)
		self.clearDMAIRQ(1)
		self.disarmDMAChannel(0)
		self.disarmDMAChannel(1)
		flashRetries = 0

		# Split in 2048-byte chunks
		iOfs = 0
		while (iOfs < len(data)):

			# Check if we should show progress
			if showProgress:
				print "%0.0f%%..." % (iOfs*100/len(data)),
				sys.stdout.flush()

			# Get next page
			iLen = min( len(data) - iOfs, self.bulkBlockSize )

			# Update DMA configuration if we have less than bulk-block size data 
			if (iLen < self.bulkBlockSize):
				self.configDMAChannel( 0, 0x6260, 0x0000, 0x1F, tlen=iLen, srcInc=0, dstInc=1, priority=1, interrupt=True )
				self.configDMAChannel( 1, 0x0000, 0x6273, 0x12, tlen=iLen, srcInc=1, dstInc=0, priority=2, interrupt=True )

			# Upload to RAM through DMA-0
			self.armDMAChannel(0)
			self.brustWrite( data[iOfs:iOfs+iLen] )

			# Wait until DMA-0 raises interrupt
			while not self.isDMAIRQ(0):
				time.sleep(0.010)

			# Clear DMA IRQ flag
			self.clearDMAIRQ(0)

			# Calculate the page where this data belong to
			fAddr = offset + iOfs
			fPage = int( fAddr / self.flashPageSize )

			# Calculate FLASH address High/Low bytes
			# for writing (addressable as 32-bit words)
			fWordOffset = int(fAddr / 4)
			cHigh = (fWordOffset >> 8) & 0xFF
			cLow = fWordOffset & 0xFF
			self.writeXDATA( 0x6271, [cLow, cHigh] )

			# Debug
			#print "[@%04x: p=%i, ofs=%04x, %02x:%02x]" % (fAddr, fPage, fWordOffset, cHigh, cLow),
			#sys.stdout.flush()

			# Check if we should erase page first
			if erase:
				# Select the page to erase using FADDRH[7:1]
				#
				# NOTE: Specific to (CC2530, CC2531, CC2540, and CC2541),
				#       the CC2533 uses FADDRH[6:0]
				#
				cHigh = (fPage << 1)
				cLow = 0
				self.writeXDATA( 0x6271, [cLow, cHigh] )
				# Set the erase bit
				self.setFlashErase()
				# Wait until flash is not busy any more
				while self.isFlashBusy():
					time.sleep(0.010)

			# Upload to FLASH through DMA-1
			self.armDMAChannel(1)
			self.setFlashWrite()

			# Wait until DMA-1 raises interrupt
			while not self.isDMAIRQ(1):
				# Also check for errors
				if self.isFlashAbort():
					self.disarmDMAChannel(1)
					raise IOError("Flash page 0x%02x is locked!" % fPage)
				time.sleep(0.010)

			# Clear DMA IRQ flag
			self.clearDMAIRQ(1)

			# Check if we should verify
			if verify:
				verifyBytes = self.readCODE(fAddr, iLen)
				for i in range(0, iLen):
					if verifyBytes[i] != data[iOfs+i]:
						if flashRetries < 3:
							print "[Flash Error @0x%04x, will retry]" % (fAddr+i),
							flashRetries += 1
							continue
						else:
							raise IOError("Flash verification error on offset 0x%04x" % (fAddr+i))
			flashRetries = 0

			# Forward to next page
			iOfs += iLen

		if showProgress:
			print "ok"

def renderDebugConfig(cfg):
	"""
	Visualize debug config
	"""
	if (cfg & 0x10) != 0:
		print " [X] SOFT_POWER_MODE"
	else:
		print " [ ] SOFT_POWER_MODE"
	if (cfg & 0x08) != 0:
		print " [X] TIMERS_OFF"
	else:
		print " [ ] TIMERS_OFF"
	if (cfg & 0x04) != 0:
		print " [X] DMA_PAUSE"
	else:
		print " [ ] DMA_PAUSE"
	if (cfg & 0x02) != 0:
		print " [X] TIMER_SUSPEND"
	else:
		print " [ ] TIMER_SUSPEND"

def renderDebugStatus(cfg):
	"""
	Visualize debug status
	"""
	if (cfg & 0x80) != 0:
		print " [X] CHIP_ERASE_BUSY"
	else:
		print " [ ] CHIP_ERASE_BUSY"
	if (cfg & 0x40) != 0:
		print " [X] PCON_IDLE"
	else:
		print " [ ] PCON_IDLE"
	if (cfg & 0x20) != 0:
		print " [X] CPU_HALTED"
	else:
		print " [ ] CPU_HALTED"
	if (cfg & 0x10) != 0:
		print " [X] PM_ACTIVE"
	else:
		print " [ ] PM_ACTIVE"
	if (cfg & 0x08) != 0:
		print " [X] HALT_STATUS"
	else:
		print " [ ] HALT_STATUS"
	if (cfg & 0x04) != 0:
		print " [X] DEBUG_LOCKED"
	else:
		print " [ ] DEBUG_LOCKED"
	if (cfg & 0x02) != 0:
		print " [X] OSCILLATOR_STABLE"
	else:
		print " [ ] OSCILLATOR_STABLE"
	if (cfg & 0x01) != 0:
		print " [X] STACK_OVERFLOW"
	else:
		print " [ ] STACK_OVERFLOW"

