/**
 * s10-syx2qd
 * Version 1.0 - 2021-10-12
 * D Cooper Dalrymple - https://dcdalrymple.com/
 */

/**
 * References:
 * - https://github.com/encore64/s10-syx2wav/blob/master/main.c
 * - https://github.com/keirf/FlashFloppy/blob/master/src/image/qd.c
 */

#include <stdio.h>
#include <stdlib.h>

#include "global.h"
#include "syx.h"
#include "qd.h"

int main(int argc, char *argv[]) {

	char verbose = 0;

	if (verbose) printf("*** Roland S-10 .syx to .qd conversion ***\n");

	if (argc < 2) {
		printf("\nError: Too few arguments.\nSyntax should be: s10-syx2qd input.syx\n");
		return 1;
	}

    SyxData *syxdata = read_syx(argv[1]);
    if (!syxdata) return 1;

    Sample *sample = convert_syx_to_sample(syxdata, verbose);
    if (!sample) return 1;

	if (verbose) printf("\n");

	return 0;
}
