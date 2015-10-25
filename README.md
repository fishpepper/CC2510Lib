CC2510Lib
=====

this is a fork of the CCLib (https://github.com/wavesoft/CCLib)

STATUS: WORK IN PROGRESS! NOT YET WORKING!

working:
- connecting
- cc_info.py
- erase chip
- write & verify flash using cc_write_flash.py (tested with hex from sdcc)

i ported it to support programming of a cc2510f16 chip. adding cc251x support is trivial, see ccdebugger.py and chip id code

Wiring
------

The arduino library is tailored for 5V Teensy/Arduino chips, and therefore provide two separate DD pins, for use with voltage dividers to 3.3V.

Start with the **CCLib_proxy** example from CCLib and change the pin configuration in order to match your setup. For your reference, here is the wiring diagram with voltage dividers.

    For the DD Pin:
    
     <CC_DD_O> --[ 2k2 ]-- <CC_DD_I> --[ 3k3 ]-- <GND>
                                |
                               {DD}
     
    For the DC Pin:
    
     <CC_DC> --[ 2k2 ]-- {DC} --[ 3k3 ]-- <GND>
     
    For the RST Pin:
     
     <CC_DC> --[ 2k2 ]-- {RST} --[ 3k3 ]-- <GND>

Where {DD},{DC} and {RST} are the pins on the CCxxxx chip.

Usage
-----

1. Open the CCLib_proxy example.
2. Change the `LED`, `CC_RST`, `CC_DC`, `CC_DD_I` and `CC_DD_O` constants to match your configuration.
3. Flash it to your Teensy/Arduino
4. Connect it to your CCxxxx chip
5. Use the python scripts from the Python/ directory to read/flash your chip.

Protocol
--------

The protocol used between your computer and your Arduino is quite simple and not really fault-proof. This was intended as a pure proxy mechanism in order to experiment with the CC Debugging protocol from the computer. Therefore, if you interrupt any operation in the middle, you will most probably have to unplug and re-plug your Teensy/Arduino. That said, here is the protocol:

Since most of the debug commands are at max 4-bytes long, we are sending from the computer a constant-sized frame of 4-bytes:

    +-----------+-----------+-----------+-----------+
    |  Command  |   Data 0  |   Data 1  |   Data 2  |
    +-----------+-----------+-----------+-----------+

The only exception is the brust-write command (CMD_BRUSTWR), where up to 2048 bytes might follow the 4-byte frame.

The Teensy/Arduino will always reply with the following 3-byte long frame:

    +-----------+-----------+-----------+
    |   Status  |    ResH   |  Err/ResL |
    +-----------+-----------+-----------+

If the status code is `ANS_OK`, the `ResH:ResL` word contains the resulting word (or byte) of the command. If it's `ANS_ERR`, the `ResL` byte contains the error code.


Disclaimer
----------

i sucessfully flashed a cc2510f16 chip with the scripts provided with this project, however I DO NOT GURANTEE THAT THIS WILL WORK IN YOUR CASE. **YOU ARE USING THIS CODE SOLELY AT YOUR OWN RISK!**

License
-------

Copyright (c) 2015 Simon Schulz - github.com/fishpepper

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.
 
You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.

