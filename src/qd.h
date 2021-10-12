#ifndef QD_H_
#define QD_H_

#include <stdint.h>

struct disk_header {
    char sig[8];        /* ...QD... */
};

struct track_header {
    uint32_t offset;    /* Byte offset to track data */
    uint32_t len;       /* Byte length of track data */
    uint32_t win_start; /* Byte offset of read/write window start */
    uint32_t win_end;   /* Byte offset of read/write window end */
};

#endif
