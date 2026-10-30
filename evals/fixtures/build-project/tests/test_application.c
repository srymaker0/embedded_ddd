#include <assert.h>
#include "sensor.h"

int main(void)
{
    assert(sample_is_negative(0x0fffU));
    assert(!sample_is_negative(1U));
    return 0;
}
