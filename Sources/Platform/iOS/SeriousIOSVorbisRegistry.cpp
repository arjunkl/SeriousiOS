#include "SeriousIOSStaticRegistry.h"

#include <vorbis/vorbisfile.h>

#include <cstring>
#include <type_traits>

namespace {

template <typename Function>
void* functionAddress(Function function) {
    static_assert(std::is_pointer<Function>::value, "function pointer required");
    static_assert(sizeof(Function) == sizeof(void*), "unexpected function pointer size");
    void* address = nullptr;
    std::memcpy(&address, &function, sizeof(address));
    return address;
}

struct VorbisRegistrar {
    VorbisRegistrar() {
        SeriousIOS_RegisterStaticSymbol("ov_clear", functionAddress(&ov_clear));
        SeriousIOS_RegisterStaticSymbol("ov_open", functionAddress(&ov_open));
        SeriousIOS_RegisterStaticSymbol(
            "ov_open_callbacks",
            functionAddress(&ov_open_callbacks));
        SeriousIOS_RegisterStaticSymbol("ov_read", functionAddress(&ov_read));
        SeriousIOS_RegisterStaticSymbol("ov_info", functionAddress(&ov_info));
        SeriousIOS_RegisterStaticSymbol(
            "ov_time_seek",
            functionAddress(&ov_time_seek));
    }
};

VorbisRegistrar gVorbisRegistrar;

} // namespace
