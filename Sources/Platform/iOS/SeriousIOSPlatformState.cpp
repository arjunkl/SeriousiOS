#include "SeriousIOSPlatformBridge.h"

#include <atomic>
#include <mutex>
#include <string>
#include <utility>

namespace {

struct PathState {
    std::string executable;
    std::string data;
    std::string user;
    std::string cache;
    std::string temporary;
    bool configured = false;
};

std::mutex gPathMutex;
PathState gPaths;
std::atomic<void*> gGLContext{nullptr};
std::atomic<SeriousIOSMakeCurrentCallback> gMakeCurrentCallback{nullptr};

std::string normalizedPath(const char* value, bool directory) {
    if (value == nullptr || *value == '\0') {
        return {};
    }

    std::string path(value);
    if (directory && path.back() != '/') {
        path.push_back('/');
    }
    return path;
}

const char* pathPointer(const std::string PathState::*member) {
    std::lock_guard<std::mutex> lock(gPathMutex);
    return (gPaths.*member).c_str();
}

} // namespace

extern "C" bool SeriousIOS_ConfigurePaths(
    const char* executablePath,
    const char* dataPath,
    const char* userPath,
    const char* cachePath,
    const char* temporaryPath) {
    PathState next;
    next.executable = normalizedPath(executablePath, false);
    next.data = normalizedPath(dataPath, true);
    next.user = normalizedPath(userPath, true);
    next.cache = normalizedPath(cachePath, true);
    next.temporary = normalizedPath(temporaryPath, true);
    next.configured = !next.executable.empty()
        && !next.data.empty()
        && !next.user.empty()
        && !next.cache.empty()
        && !next.temporary.empty();
    if (!next.configured) {
        return false;
    }

    std::lock_guard<std::mutex> lock(gPathMutex);
    if (gPaths.configured) {
        return gPaths.executable == next.executable
            && gPaths.data == next.data
            && gPaths.user == next.user
            && gPaths.cache == next.cache
            && gPaths.temporary == next.temporary;
    }
    gPaths = std::move(next);
    return true;
}

extern "C" bool SeriousIOS_ArePathsConfigured(void) {
    std::lock_guard<std::mutex> lock(gPathMutex);
    return gPaths.configured;
}

extern "C" const char* SeriousIOS_GetExecutablePath(void) {
    return pathPointer(&PathState::executable);
}

extern "C" const char* SeriousIOS_GetDataPath(void) {
    return pathPointer(&PathState::data);
}

extern "C" const char* SeriousIOS_GetUserPath(void) {
    return pathPointer(&PathState::user);
}

extern "C" const char* SeriousIOS_GetCachePath(void) {
    return pathPointer(&PathState::cache);
}

extern "C" const char* SeriousIOS_GetTemporaryPath(void) {
    return pathPointer(&PathState::temporary);
}

extern "C" void SeriousIOS_SetGLContext(
    void* context,
    SeriousIOSMakeCurrentCallback makeCurrentCallback) {
    gGLContext.store(context, std::memory_order_release);
    gMakeCurrentCallback.store(makeCurrentCallback, std::memory_order_release);
}

extern "C" void* SeriousIOS_GetGLContext(void) {
    return gGLContext.load(std::memory_order_acquire);
}

extern "C" int SeriousIOS_MakeGLContextCurrent(void) {
    SeriousIOSMakeCurrentCallback callback =
        gMakeCurrentCallback.load(std::memory_order_acquire);
    void* context = gGLContext.load(std::memory_order_acquire);
    if (callback == nullptr || context == nullptr) {
        return -1;
    }
    return callback(context);
}
