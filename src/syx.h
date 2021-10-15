#ifndef SYX_H_
#define SYX_H_

#include <stdint.h>
#include <string.h>
#include <errno.h>

#define S10_MEMORY_MAX (256*1024)

#define SAMPLE_BANKS (4)
#define SAMPLING_STRUCTURE_MAX (10)
#define TONE_NAME_LENGTH (10)
#define SAMPLING_STRUCTURE_LUT_LENGTH (8)

#define SAMPLE_RATE_30K (30000)
#define SAMPLE_RATE_15K (15000)
#define DEFAULT_SAMPLE_RATE (SAMPLE_RATE_30K)

typedef struct SyxDatas {
    uint32_t size;
    uint8_t *buffer;
} SyxData;

static const char* const SamplingStructureLUT[] = {
    "A",
    "B",
    "C",
    "D",
    "AB",
    "CD",
    "ABCD",
    "A-B",
    "C-D",
    "AB-CD",
    "A-B-C-D"
};

// Sampling structure array - bank offset, length, loops
static const uint8_t SSBankOffsetLengthLoops[][3] = {
    {0, 1, 1},
    {1, 1, 1},
    {2, 1, 1},
    {3, 1, 1},
    {0, 2, 1},
    {2, 2, 1},
    {0, 4, 1},
    {0, 1, 2},
    {2, 1, 2},
    {0, 2, 2},
    {0, 1, 4}
};

typedef struct SamplingStructures {
    uint8_t Index;
    uint8_t BankOffset;
    uint8_t Length;
    uint8_t Loops;
} SamplingStructure;

typedef struct Samples {
    SamplingStructure GlobalSamplingStructure;
    char ToneName[SAMPLE_BANKS][TONE_NAME_LENGTH];
    SamplingStructure SamplingStructure[SAMPLE_BANKS];
    uint8_t LoopMode[SAMPLE_BANKS];
    uint8_t ScanMode[SAMPLE_BANKS];
    uint32_t RecKey[SAMPLE_BANKS];
    uint32_t StartAddress[SAMPLE_BANKS];
    uint32_t ManualLoopLength[SAMPLE_BANKS];
    uint32_t ManualEndAddress[SAMPLE_BANKS];
    uint32_t AutoLoopLength[SAMPLE_BANKS];
    uint32_t AutoEndAddress[SAMPLE_BANKS];
    uint32_t SampleRate[SAMPLE_BANKS];
    uint8_t *Memory;
} Sample;

Sample *init_sample(void);
SamplingStructure get_sampling_structure(uint8_t);
SyxData *read_syx(char *);
Sample *convert_syx_to_sample(SyxData *, char);

#endif
