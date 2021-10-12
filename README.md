# Roland S-10 .syx to .wav conversion

Takes a sysex-file intended for the Roland S-10 (12 bit) sampler, analyzes the sysex data and writes a virtual disk file `*.qd` meant for the Gotek floppy emulator with the [FlashFloppy](https://github.com/keirf/FlashFloppy/wiki/Quick-Disk) or [HxC2001](https://hxc2001.com/docs/gotek-floppy-emulator-hxc-firmware/pages/quickdisk.html) QD firmware.

`$ s10-syx2qd input.syx`

The qd-filename will be based on 1) the input file, 2) the sampling structure used, 3) what wave parameter and 4) the tone name. For example, converting the file input.syx may generate `input - A-B (A) ToneName.qd`.

## Batch Converting

The program only converts one sysex-file at the time. In Linux or Windows you can create the following file and put it together with the compiled executable in order to convert a directory of .syx-files (plus all its subdirectories) to .qd.

### Linux

**batch-convert.sh**
```bash
#!/bin/bash
find "./" -type f -name "*.syx" | while read fname; do
  ./s10-syx2wav "$fname"
done
```

### Windows

**batch-convert.bat**
```bat
for /r %%i in (*.syx) do s10-syx2wav.exe "%%i"
```

## Credits

This repository was inspired by [s10-syx2wav](https://github.com/encore64/s10-syx2wav) created by [encore64](https://github.com/encore64).
