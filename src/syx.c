#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include "syx.h"
#include "global.h"

SamplingStructure get_sampling_structure(uint8_t i) {
    SamplingStructure ss;
    ss.Index = i;
    ss.BankOffset = SSBankOffsetLengthLoops[i][0];
    ss.Length = SSBankOffsetLengthLoops[i][1];
    ss.Loops = SSBankOffsetLengthLoops[i][2];
    return ss;
}

Sample *init_sample(void) {
    Sample *sample = malloc(sizeof(*sample));

    sample->GlobalSamplingStructure = NULL;

    uint8_t i, j;
    for (i = 0; i < SAMPLE_BANKS; i++) {
        for (j = 0; j < TONE_NAME_LENGTH-1; j++) {
            sample->ToneName[i][j] = ' ';
        }
        sample->ToneName[i][TONE_NAME_LENGTH-1] = '\0';

        sample->SamplingStructure[i] = get_sampling_structure(0);
        sample->LoopMode[i] = 0;
        sample->ScanMode[i] = 0;
        sample->RecKey[i] = 0;
        sample->StartAddress[i] = 0;
        sample->ManualLoopLength[i] = 0;
        sample->ManualEndAddress[i] = 0;
        sample->AutoLoopLength[i] = 0;
        sample->AutoEndAddress[i] = 0;
        sample->SampleRate[i] = DEFAULT_SAMPLE_RATE;
    }

    sample->Memory = (uint8_t *) malloc(S10_MEMORY_MAX);
	if (!sample->Memory) {
		printf("Memory allocation error.\n");
		return NULL;
	}

    return sample;
}

SyxData *read_syx(char *filepath) {
    FILE *file;
    SyxData *syx = malloc(sizeof(*syx));

    // Open file for reading
    if (!(file = fopen(filepath, "rb"))) {
	    printf("Error opening file: %s\n", strerror(errno));
	    return NULL;
	}

    // Check length of file
    fseek(file, 0, SEEK_END);
	syx->size = ftell(file);
	rewind(file);

    // Allocate memory
    syx->buffer = (uint8_t *) malloc(syx->size);
	if (!syx->buffer) {
		printf("Memory allocation error.\n");
		return NULL;
	}

    // Read file into buffer
    fread(syx->buffer, 1, syx->size, file);
	fclose(file);

    return syx;
}

Sample *convert_syx_to_sample(SyxData *syx, char verbose) {

    Sample *sample = init_sample();
    if (!sample) return NULL; // Memory Allocation

    uint8_t sampleToggle;
    uint32_t samplePosition;
    int sampleData;

    uint8_t syxByte;
	uint32_t syxCounter = 0;
	uint8_t syxActive = 0;
    size_t x;
	uint32_t Address;

    uint8_t syxCommand;
	uint8_t syxParam;

    int wpOffs;	// Wave Parameter Offset
	uint8_t wpBlock; // Wave Parameter Block

    for (x = 0; x < syx->size; x++) {
        syxByte = syx->buffer[x];

        // Sysex Start
        if (syxByte == 0xf0) {
            if (verbose > 1) printf("\nSystem Exclusive start.\n");
            syxCounter = 0;
            syxActive = 1;
            continue;
        }

        // Sysex Stop
        if (syxByte == 0xf7) {
            if (verbose > 1) printf("System Exclusive stop. SysexCounter (minus header and stop) at: %u\n", syxCounter-8);
            syxActive = 0;
            continue;
        }

        if (syxActive) {

            // Manufacturer ID
            if (syxCounter == 0) {
                if (syxByte != 0x41) { // Wrong manufacturer ID (not Roland)
                    if (verbose > 1) printf("Wrong manufacturer ID.\n");
                    syxActive = 0;
                } else {
                    if (verbose > 1) printf("Roland ID found.\n");
                }
                syxCounter++;
                continue;
            }

            // MIDI Channel
            if (syxCounter == 1) {
                if (syxByte > 0x0f) {
                    if (verbose > 1) printf("Wrong MIDI basic channel.\n");
                    syxActive = 0;
                } else {
                    if (verbose > 1) printf("MIDI basic channel: %d\n", syxByte+1);
                }
                syxCounter++;
                continue;
            }

            // Model ID
            if (syxCounter == 2) {
                if (syxByte != 0x10) {
                    if (verbose > 1) printf("Wrong Model-ID.\n");
                    syxActive = 0;
                } else {
                    if (verbose > 1) printf("S-10 found.\n");
                }
                syxCounter++;
                continue;
            }

            // Command ID
            if (syxCounter == 3) {
                syxCommand = syxByte;

                if (verbose > 1) {
                    switch (syxCommand) {
                        case 0x11: // RQ1
                            printf("Command-ID: Request (one way).\n");
                            break;
        				case 0x12: // DT1
        					printf("Command-ID: Data set (One way).\n");
                            break;
        				case 0x40: // WSD
        					printf("Command-ID: Want to send data.\n");
                            break;
        				case 0x41: // RQD
        					printf("Command-ID: Request data.\n");
                            break;
        				case 0x42: // DAT
        					printf("Command-ID: Data set.\n");
                            break;
        				case 0x43: // ACK
        					printf("Command-ID: Acknowledge.\n");
                            break;
        				case 0x45: // EOD
        					printf("Command-ID: End of data.\n");
                            break;
        				case 0x4e: // ERR
        					printf("Command-ID: Communication error.\n");
                            break;
        				case 0x4f: // RJC
        					printf("Command-ID: Rejection.\n");
                            break;
                    }
                }

                syxCounter++;
                continue;
            }

            // Address (only DT1)
            if (syxCounter == 4 && syxCommand == 0x12) {
                if (verbose > 1) printf("Address: %02hhX %02hhX %02hhX ", syx->buffer[x], syx->buffer[x+1], syx->buffer[x+2]);

                Address = (syx->buffer[x]<<16) + (syx->buffer[x+1]<<8) + syx->buffer[x+2];
                syxParam = 0;
                sampleToggle = 0;
                wpOffs = 0x00; // reset Wave Parameter Offset

                // Wave Parameter
                if (Address >= 0x00010000 && Address <= 0x00010048) {
                    syxParam = 1; wpBlock = 0;
                    if (verbose) printf("Wave parameter of block-1.\n");
                }
                if (Address >= 0x00010049 && Address <= 0x00010111) {
                    syxParam = 1; wpBlock = 1;
                    if (verbose) printf("Wave parameter of block-2.\n");
                }
                if (Address >= 0x00010112 && Address <= 0x0001015a) {
                    syxParam = 1; wpBlock = 2;
                    if (verbose) printf("Wave parameter of block-3.\n");
                }
                if (Address >= 0x0001015b && Address <= 0x00010224) {
                    syxParam = 1; wpBlock = 3;
                    if (verbose) printf("Wave parameter of block-4.\n");
                }
                if ((syx->buffer[x] == 0x01) && (syx->buffer[x+1] == 0x08)) {
                    syxParam = 2;
                    if (verbose) printf("Performance parameter.\n");
                }

                // Wave Data
                if ((syx->buffer[x] >= 0x02) && (syx->buffer[x] <= 0x11)) {
                    syxParam = 3;
                    samplePosition = ((syx->buffer[x] - 0x02) << 14) + (syx->buffer[x+1] << 7) + syx->buffer[x+2];
                }

                if ((syx->buffer[x] >= 0x02) && (syx->buffer[x] <= 0x05)) {
                    if (verbose > 1) printf("Wave data of bank-1.\n");
                }
                if ((syx->buffer[x] >= 0x06) && (syx->buffer[x] <= 0x09)) {
                    if (verbose > 1) printf("Wave data of bank-2.\n");
                }
                if ((syx->buffer[x] >= 0x0a) && (syx->buffer[x] <= 0x0d)) {
                    if (verbose > 1) printf("Wave data of bank-3.\n");
                }
                if ((syx->buffer[x] >= 0x0e) && (syx->buffer[x] <= 0x11)) {
                    if (verbose > 1) printf("Wave data of bank-4.\n");
                }

            }

            if (syxCounter >= 7) {

                // Wave Parameter
                if (syxParam == 1) {
                    if (syxCounter == 7+0x49) { // When a second wave parameter block is in the same sysex chunk
                        if (syx->buffer[x+1] == 0xf7) { // if next symbol is system exclusive stop, this is a stray symbol
                            if (verbose) printf("Stray symbol (next is system exclusive stop). Ignoring.\n");
                            syxActive = 0;
                            continue;
                        }
                        wpOffs = 0x49;

                        if (verbose > 1) printf("WPOffs is: %d\n", wpOffs);
                    }

                    // Destination Bank
                    if (syxCounter == 7+wpOffs) {
                        wpBlock = syx->buffer[x+0x0a]; // Destination bank (we set this early / first as we rely on it instead of memory address)
                        if (verbose) printf("Destination bank: %d\n", wpBlock+1);
                        if (wpBlock > SAMPLE_BANKS) {
                            if (verbose) printf("WPBlock error. Ignoring.\n");
                            syxActive = 0;
                            continue;
                        }
                    }

                    // Tone Name
                    if (syxCounter >= 7+wpOffs && syxCounter <= 7+wpOffs+0x08) {
                        if (isfilesafe(syx->buffer[x])) {
							sample->ToneName[wpBlock][syxCounter-7-wpOffs]= syx->buffer[x];
						} else {
							sample->ToneName[wpBlock][syxCounter-7-wpOffs]= ' ';
						}
                        if (syxCounter == 7+wpOffs+8) {
                            // sample->ToneName[wpBlock][9] = '\0'; // null
                            trim_whitespace(sample->ToneName[wpBlock]);

                            if (verbose) printf("Tone Name: '%s'\n", sample->ToneName[wpBlock]);
                        }
                    }

                    // Sampling Structure
                    if (syxCounter == 7+wpOffs+0x09 && syx->buffer[x] <= SAMPLING_STRUCTURE_MAX) {
                        sample->SamplingStructure[wpBlock] = get_sampling_structure(syx->buffer[x]);

                        if (!sample->GlobalSamplingStructure) sample->GlobalSamplingStructure = sample->SamplingStructure[wpBlock];

						if (verbose) {
							printf("Sampling structure: %d - %s\n", sample->SamplingStructure[wpBlock].Index, SamplingStructureLUT[sample->SamplingStructure[wpBlock].Index]);
						}
                    }

                    // (SysexCounter == 7+wpOffs+0x0a) // Destination bank

                    // Sampling rate
                    if (syxCounter == 7+wpOffs+0x0b) {
                        if (syx->buffer[x] & 0x01) {
                            sample->SampleRate[wpBlock] = SAMPLE_RATE_30K; // Defauls to 30000
                            if (verbose) printf("Sampling rate: 15 kHz\n");
                        } else {
                            if (verbose) printf("Sampling rate: 30 kHz\n");
                        }
                    }

                    // Loop Mode & Scan Mode
                    if (syxCounter == 7+wpOffs+0x0c) {
                        if ((syx->buffer[x] & 0x0c) == 0x00) {
							if (verbose) printf("Loop mode: 1 shot\n");
						}
						if ((syx->buffer[x] & 0x0c) == 0x04) {
                            sample->LoopMode[wpBlock] = 1;
							if (verbose) printf("Loop mode: Manual\n");
                        }
						if ((syx->buffer[x] & 0x0c) == 0x08) {
                            sample->LoopMode[wpBlock] = 2;
                            if (verbose) printf("Loop mode: Auto\n");
                        }

						if ((syx->buffer[x] & 0x03) == 0x00) {
                            if (verbose) printf("Scan mode: Forward\n");
                        }
						if ((syx->buffer[x] & 0x03) == 0x01) {
                            sample->ScanMode[wpBlock] = 1;
                            if (verbose) printf("Scan mode: Alternate\n");
                        }
						if ((syx->buffer[x] & 0x03) == 0x02) {
                            sample->ScanMode[wpBlock] = 2;
                            if (verbose) printf("Scan mode: Backward\n");
                        }
                    }

                    // Rec key number
                    if (syxCounter == 7+wpOffs+0x0d) {
						sample->RecKey[wpBlock] = (syx->buffer[x] & 0x0f) + ((syx->buffer[x+1] & 0x0f) << 4);
                        if (verbose) printf("Rec key number: %d\n", sample->RecKey[wpBlock]);
					}

                    // Start address, Manual and auto loop length and end address
                    if (syxCounter == 7+wpOffs+0x11) {
                        // (StartAddress-65536) / 32768 seems to be the same as destination bank
                        sample->StartAddress[wpBlock] =
                            ((syx->buffer[x] & 0x0f) << 8) +
                            ((syx->buffer[x+1] & 0x0f) << 12) +
                            ((syx->buffer[x+2] & 0x0f)) +
                            ((syx->buffer[x+3] & 0x0f) << 4) +
                            ((syx->buffer[x+21] & 0x0c) << 14);
                        if (sample->StartAddress[wpBlock] > 65535) sample->StartAddress[wpBlock] -= 65536;

                        sample->ManualLoopLength[wpBlock] =
							((syx->buffer[x+4] & 0x0f) << 8) +
							((syx->buffer[x+5] & 0x0f) << 12) +
							((syx->buffer[x+6] & 0x0f)) +
							((syx->buffer[x+7] & 0x0f) << 4) +
							((syx->buffer[x+20] & 0x0c) << 14);
                        sample->ManualLoopLength[wpBlock]--;

                        sample->ManualEndAddress[wpBlock] =
                            ((syx->buffer[x+8] & 0x0f) << 8) +
                            ((syx->buffer[x+9] & 0x0f) << 12) +
                            ((syx->buffer[x+10] & 0x0f)) +
                            ((syx->buffer[x+11] & 0x0f) << 4) +
                            ((syx->buffer[x+20] & 0x03) << 16);
                        if (sample->ManualEndAddress[wpBlock] > 65535) sample->ManualEndAddress[wpBlock] -=
                        65536;
                        sample->ManualEndAddress[wpBlock] -= sample->StartAddress[wpBlock];

                        sample->AutoLoopLength[wpBlock] =
							((syx->buffer[x+12] & 0x0f) << 8) +
							((syx->buffer[x+13] & 0x0f) << 12) +
							((syx->buffer[x+14] & 0x0f)) +
							((syx->buffer[x+15] & 0x0f) << 4) +
							((syx->buffer[x+23] & 0x0c) << 14);
						sample->AutoLoopLength[wpBlock]--;

						sample->AutoEndAddress[wpBlock] =
							((syx->buffer[x+16] & 0x0f) << 8) +
							((syx->buffer[x+17] & 0x0f) << 12) +
							((syx->buffer[x+18] & 0x0f)) +
							((syx->buffer[x+19] & 0x0f) << 4) +
							((syx->buffer[x+23] & 0x03) << 16);
						if (sample->AutoEndAddress[wpBlock] > 65535) sample->AutoEndAddress[wpBlock] -= 65536;
						sample->AutoEndAddress[wpBlock] -= sample->StartAddress[wpBlock];

						if (verbose) {
                            printf("Start Address: %u\n", sample->StartAddress[wpBlock]);
    						printf("Manual Loop Length: %u\n", sample->ManualLoopLength[wpBlock]);
    						printf("Manual End Address (minus Start Address): %u\n", sample->ManualEndAddress[wpBlock]);
    						printf("Auto Loop Length: %u\n", sample->AutoLoopLength[wpBlock]);
    						printf("Auto End Address (minus Start Address): %u\n", sample->AutoEndAddress[wpBlock]);
                        }
                    }
                }

                // Wave Data
                if (syxParam == 3) {
                    if (sampleToggle % 2 != 0) {
                        // Make sure we never write outside S-10 memory
						if (samplePosition+1 > S10_MEMORY_MAX) {
                            if (verbose) printf("SamplePosition outside S-10 memory boundary.\n");
                            break;
                        }

                        // Convert 12-bit to 16-bit?
                        sampleData = ((syx->buffer[x-1] & 0x7f) << 9) + ((syx->buffer[x] & 0x7c) << 2);
                        sample->Memory[samplePosition] = 0xff & sampleData;
						sample->Memory[samplePosition+1] = 0xff & (sampleData >> 8);

						samplePosition+=2;
					}
					sampleToggle++;
                }
            }

            syxCounter++;
        }
    }

    if (verbose) printf("Final SamplePosition: %u\n", samplePosition);

    return sample;
}
