#include <stdio.h>
#include <stdlib.h>
#include "sensor.h"

int main(int argc, char **argv)
{
    if (argc != 2) {
        fprintf(stderr, "usage: sample RAW_INTEGER\n");
        return 2;
    }
    printf("%d\n", sensor_decode((unsigned int)strtoul(argv[1], NULL, 0)));
    return 0;
}
