#include <ctype.h>
#include <string.h>
#include "global.h"

// String Functions

char *strip_ext(char *str) {
	// pointer to end of string
    char *end = str + strlen(str);

    while (end > str && *end != '.' && *end != '\\' && *end != '/') {
        --end;
    }
    if ((end > str && *end == '.') && (*(end - 1) != '\\' && *(end - 1) != '/')) {
        *end = '\0';
    }

    return end;
}

char *trim_whitespace(char *str) {
	char *end;

	// Trim trailing space
	end = str + strlen(str) - 1;
	while(end > str && isspace((uint8_t)*end)) end--;

	// Write new null terminator character
	end[1] = '\0';

	return str;
}

int isfilesafe(char c) {
    return isalpha (c) ||
           isdigit (c) ||
           c == '.' ||
           c == '!' ||
           c == '(' ||
           c == ')' ||
           c == '+' ||
           c == '-' ||
           c == '_';
}

uint32_t time_to_bitofs(uint32_t cellseconds, uint32_t time)
{
	return (uint32_t)(((float)cellseconds) * (float)((float)time/(float)1000));
}

// Drive Functions

// -----------------------------------------------------------------------------
// MFM stands for "Modified frequency modulation"
// MFM      : Reversal at each '1' or between 2 '0' (at the clock place).
// Data     : 0 c 0 c 1 c 1 c 1 c 0 c 1 c 1 c 1 c 1 c 0 c 0 c 0
//               _____     ___         ___     ___       ___
// Reversal : __|     |___|   |_______|   |___|   |_____|   |___
// Cells      0 1 0 0 1 0 1 0 1 0 0 0 1 0 1 0 1 0 1 0 0 1 0 1 0
// Decoding :  | 0 | 1 | 1 | 1 | 0 | 1 | 1 | 1 | 1 | 0 | 0 | 0 |
// -----------------------------------------------------------------------------

int mfmtobin(uint8_t * input_data,int input_data_size,uint8_t * decod_data,int decod_data_size,int bit_offset,int lastbit) {
	int i,j;
	uint8_t b,c1,c2;

	i = 0;
	b = 0x80;

	bit_offset = bit_offset%input_data_size;
	j = bit_offset>>3;

	do
	{

		c1 = (uint8_t)( input_data[j] & (0x80>>(bit_offset&7)) );
		bit_offset = (bit_offset+1)%input_data_size;
		j = bit_offset>>3;

		c2 = (uint8_t)( input_data[j] & (0x80>>(bit_offset&7)) );
		bit_offset = (bit_offset+1)%input_data_size;
		j = bit_offset>>3;

		if( !c1 && c2 )
			decod_data[i] = (uint8_t)( decod_data[i] | b );
		else
			decod_data[i] = (uint8_t)( decod_data[i] & ~b );

		b = (uint8_t)( b>>1 );
		if(!b)
		{
			b=0x80;
			i++;
		}

	}while(i<decod_data_size);

	return bit_offset;
}

int bintomfm(uint8_t *track_data, int track_data_size, uint8_t *bin_data, int bin_data_size, int bit_offset) {
    int i,lastbit;
	uint8_t b;

	i = 0;
	b = 0x80;

	bit_offset = bit_offset%track_data_size;

	lastbit = 0;
	if (bit_offset) {
		if (getbit(track_data, bit_offset-1)) lastbit = 1;
	} else {
		if (getbit(track_data, track_data_size-1)) lastbit = 1;
	}

	do {

		if (bin_data[i] & b) {
			setbit(track_data,bit_offset,0);
			bit_offset = (bit_offset+1)%track_data_size;
			setbit(track_data,bit_offset,1);
			bit_offset = (bit_offset+1)%track_data_size;
			lastbit = 1;
		} else {
			if (lastbit) {
				setbit(track_data,bit_offset,0);
				bit_offset = (bit_offset+1)%track_data_size;
				setbit(track_data,bit_offset,0);
				bit_offset = (bit_offset+1)%track_data_size;
			} else {
				setbit(track_data,bit_offset,1);
				bit_offset = (bit_offset+1)%track_data_size;
				setbit(track_data,bit_offset,0);
				bit_offset = (bit_offset+1)%track_data_size;
			}
			lastbit = 0;
		}

		b = (uint8_t)( b >> 1 );
		if (!b) {
			b = 0x80;
			i++;
		}

	} while (i<bin_data_size);

	return bit_offset;
}

int getbit(uint8_t * input_data, int bit_offset) {
    return ((input_data[bit_offset>>3] >> (0x7 - (bit_offset&0x7)))) & 0x01;
}

void setbit(uint8_t * input_data, int bit_offset, int state) {
    if (state) {
        input_data[bit_offset>>3] = (uint8_t)(input_data[bit_offset>>3] | (0x80 >> (bit_offset&0x7)));
    } else {
        input_data[bit_offset>>3] = (uint8_t)(input_data[bit_offset>>3] & ~(0x80 >> (bit_offset&0x7)));
    }
    return;
}

// LUT Functions

void init_lut(uint8_t verbose) {
    uint16_t i;
    for (i = 0; i < LUT_SIZE; i++) {
        LUT_ByteBitsInverterPost[LUT_ByteBitsInverterPre[i]] = i & 0xff;
    }
    if (verbose>1) {
        printf("Inverted LUT Table:\n");
        for (i = 0; i < LUT_SIZE/8; i++) {
            printf("%x, %x, %x, %x, %x, %x, %x, %x", LUT_ByteBitsInverterPost[i*8+0], LUT_ByteBitsInverterPost[i*8+1], LUT_ByteBitsInverterPost[i*8+2], LUT_ByteBitsInverterPost[i*8+3], LUT_ByteBitsInverterPost[i*8+4], LUT_ByteBitsInverterPost[i*8+5], LUT_ByteBitsInverterPost[i*8+6], LUT_ByteBitsInverterPost[i*8+7]);
            if (i < (LUT_SIZE/8)-1) printf(",");
            printf("\n");
        }
        printf("\n");
    }
}

void lut_block(uint8_t *block, uint32_t size) {
    uint32_t i;
    for (i = 0; i < size; i++) {
        block[i] = LUT_ByteBitsInverterPost[block[i]];
    }
}

// CRC Functions

uint16_t check_crc(uint8_t *buffer, uint32_t size) {
    uint8_t high, low;
    uint8_t table[32];
    uint32_t i;

    init_crc(&high, &low, table, 0x8005, 0x0000);

    for (i = 0; i < size; i++) {
        update_crc(&high, &low, buffer[i], (uint8_t *)&table);
    }

    return ((uint16_t)high<<8) | (low & 0xff); // >0 = bad crc
}

void init_crc(uint8_t *high, uint8_t *low, uint8_t *table, uint16_t polynome, uint16_t initvalue) {
    uint16_t i, count, value;
    count = 1 << CRC_BITS;
    for (i = 0; i < count; i++) {
        value = generate_crc_table_entry(i, CRC_BITS, polynome);
        table[i+count] = (uint8_t)(value>>8);
        table[i] = (uint8_t)(value&0xff);
    }

    // Initialize the CRC to 0xffff for CCIT specs
    *high = (uint8_t)(initvalue>>8);
    *low = (uint8_t)(initvalue&0xff);
}

uint16_t generate_crc_table_entry(const uint16_t index, const uint16_t bits, const uint16_t polynome) {
    int32_t i;
    uint16_t value;

    // Prepare initial register so that index is at the MSB
    value = index;
    value <<= 16 - bits;

    for (i = 0; i < bits; i++) {
        if (value & 0x8000) {
            value = (uint16_t)((value<<1) ^ polynome);
        } else {
            value = (uint16_t)(value<<1);
        }
    }

    return value;
}

void update_crc(uint8_t *high, uint8_t *low, uint8_t value, uint8_t *table) {
    update_crc_nibble(high, low, (uint8_t)((value>>4)&0x0f), table);
    update_crc_nibble(high, low, (uint8_t)(value&0x0f), table);
}

void update_crc_nibble(uint8_t *high, uint8_t *low, uint8_t value, uint8_t *table) { // only 4 bits
    uint8_t t;

    // Step one, extract the Most significant 4 bits of the CRC register
	t = (uint8_t)((*CRC16_High) >> 4);

	// XOR in the Message Data into the extracted bits
	t = (uint8_t)(t ^ value);

	// Shift the CRC Register left 4 bits
	*CRC16_High = (uint8_t)((*CRC16_High << 4) | (*CRC16_Low >> 4));
	*CRC16_Low = (uint8_t)(*CRC16_Low << 4);

	// Do the table lookups and XOR the result into the CRC Tables
	*CRC16_High = (uint8_t)(*CRC16_High ^ crctable[t+16]);
	*CRC16_Low = (uint8_t)(*CRC16_Low ^ crctable[t]);
}
