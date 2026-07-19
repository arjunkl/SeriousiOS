#include <Engine/Base/Types.h>

#ifndef PLATFORM_IOS
#error "Serious Engine did not identify the iPhoneOS target as PLATFORM_IOS"
#endif

#ifdef PLATFORM_MACOSX
#error "iPhoneOS must not inherit PLATFORM_MACOSX"
#endif

#ifndef PLATFORM_UNIX
#error "iPhoneOS must retain Serious Engine Unix platform semantics"
#endif

#ifndef PLATFORM_64BIT
#error "arm64 iPhoneOS must be detected as a 64-bit target"
#endif

static_assert(PLATFORM_NOT_X86 == 1, "arm64 iPhoneOS cannot use x86 paths");
static_assert(sizeof(void*) == 8, "SeriousiOS requires a 64-bit target");
static_assert(sizeof(SLONG) == 4, "serialized SLONG layout must remain 32-bit");
static_assert(sizeof(ULONG) == 4, "serialized ULONG layout must remain 32-bit");
static_assert(
    sizeof(ASMSYM(SeriousIOSProbe)) == sizeof("_SeriousIOSProbe"),
    "Mach-O symbols must retain the Apple underscore prefix"
);

int main() {
    return 0;
}
