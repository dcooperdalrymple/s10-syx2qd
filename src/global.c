#include <ctype.h>
#include <string.h>
#include "global.h"

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
	while(end > str && isspace((unsigned char)*end)) end--;

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
