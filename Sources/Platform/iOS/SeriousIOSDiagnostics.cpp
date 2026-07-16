#include "SeriousIOSDiagnostics.h"
#include "SeriousIOSPlatformBridge.h"

#include <atomic>
#include <chrono>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <pthread.h>
#include <sys/stat.h>

namespace {

constexpr long long kMaximumLogBytes = 1024LL * 1024LL;
constexpr unsigned long long kPeriodicFrameInterval = 600ULL;
constexpr unsigned long long kDetailedTextureUploadLimit = 16ULL;

std::mutex gLogMutex;
FILE* gLogFile = nullptr;
char gLogPath[2048] = {};
char gEncounter[128] = "unknown";
char gBuildIdentifier[128] = "unknown";
std::chrono::steady_clock::time_point gStartTime;
std::atomic<unsigned long long> gFramesPresented{0};
std::atomic<unsigned long long> gTextureUploads{0};
std::atomic<unsigned long long> gNormalizedTextureUploads{0};
std::atomic<unsigned long long> gTextureUploadErrors{0};
std::atomic<unsigned long long> gTextureParameterNormalizations{0};
std::atomic<unsigned long long> gSuspends{0};
std::atomic<unsigned long long> gResumes{0};
std::atomic<bool> gInitialized{false};

long long fileSize(const char* path) {
    struct stat information = {};
    if (path == nullptr || stat(path, &information) != 0) {
        return 0;
    }
    return static_cast<long long>(information.st_size);
}

void makeSiblingPath(const char* base, const char* suffix, char* destination, size_t capacity) {
    std::snprintf(destination, capacity, "%s%s", base, suffix);
    destination[capacity - 1] = '\0';
}

void rotateLogsIfNeeded(const char* path) {
    if (fileSize(path) < kMaximumLogBytes) {
        return;
    }

    char first[2048] = {};
    char second[2048] = {};
    makeSiblingPath(path, ".1", first, sizeof(first));
    makeSiblingPath(path, ".2", second, sizeof(second));
    std::remove(second);
    std::rename(first, second);
    std::rename(path, first);
}

void formatWallClock(char* destination, size_t capacity) {
    const std::time_t now = std::time(nullptr);
    struct tm utc = {};
    gmtime_r(&now, &utc);
    std::strftime(destination, capacity, "%Y-%m-%dT%H:%M:%SZ", &utc);
}

unsigned long long elapsedMilliseconds() {
    const auto elapsed = std::chrono::steady_clock::now() - gStartTime;
    return static_cast<unsigned long long>(
        std::chrono::duration_cast<std::chrono::milliseconds>(elapsed).count());
}

void writeLineLocked(const char* category, const char* message, bool flush) {
    if (gLogFile == nullptr) {
        return;
    }

    char timestamp[64] = {};
    formatWallClock(timestamp, sizeof(timestamp));
    const unsigned int thread = pthread_mach_thread_np(pthread_self());
    std::fprintf(
        gLogFile,
        "%s +%llums [thread=%u] [%s] %s\n",
        timestamp,
        elapsedMilliseconds(),
        thread,
        category == nullptr ? "runtime" : category,
        message == nullptr ? "" : message);
    if (flush) {
        std::fflush(gLogFile);
    }
}

void logFormatted(const char* category, bool flush, const char* format, va_list arguments) {
    char message[4096] = {};
    std::vsnprintf(
        message,
        sizeof(message),
        format == nullptr ? "" : format,
        arguments);
    message[sizeof(message) - 1] = '\0';

    std::lock_guard<std::mutex> lock(gLogMutex);
    writeLineLocked(category, message, flush);
}

void writeBuildInfoFile(const char* root) {
    if (root == nullptr || *root == '\0') {
        return;
    }

    char path[2048] = {};
    std::snprintf(path, sizeof(path), "%sSeriousIOS-build-info.txt", root);
    path[sizeof(path) - 1] = '\0';

    FILE* file = std::fopen(path, "wb");
    if (file == nullptr) {
        return;
    }
    std::fprintf(file, "encounter=%s\n", gEncounter);
    std::fprintf(file, "build=%s\n", gBuildIdentifier);
    std::fprintf(file, "data_path=%s\n", SeriousIOS_GetDataPath());
    std::fprintf(file, "user_path=%s\n", SeriousIOS_GetUserPath());
    std::fprintf(file, "cache_path=%s\n", SeriousIOS_GetCachePath());
    std::fprintf(file, "temporary_path=%s\n", SeriousIOS_GetTemporaryPath());
    std::fflush(file);
    std::fclose(file);
}

} // namespace

extern "C" bool SeriousIOS_DiagnosticsInitialize(
    const char* encounter,
    const char* buildIdentifier) {
    std::lock_guard<std::mutex> lock(gLogMutex);
    if (gInitialized.load(std::memory_order_acquire)) {
        return true;
    }

    const char* root = SeriousIOS_GetUserPath();
    if (root == nullptr || *root == '\0') {
        return false;
    }

    std::snprintf(gEncounter, sizeof(gEncounter), "%s", encounter == nullptr ? "unknown" : encounter);
    std::snprintf(
        gBuildIdentifier,
        sizeof(gBuildIdentifier),
        "%s",
        buildIdentifier == nullptr ? "unknown" : buildIdentifier);
    gEncounter[sizeof(gEncounter) - 1] = '\0';
    gBuildIdentifier[sizeof(gBuildIdentifier) - 1] = '\0';

    std::snprintf(gLogPath, sizeof(gLogPath), "%sSeriousIOS.log", root);
    gLogPath[sizeof(gLogPath) - 1] = '\0';
    rotateLogsIfNeeded(gLogPath);

    gLogFile = std::fopen(gLogPath, "ab");
    if (gLogFile == nullptr) {
        gLogPath[0] = '\0';
        return false;
    }
    std::setvbuf(gLogFile, nullptr, _IOLBF, 0);
    gStartTime = std::chrono::steady_clock::now();
    gFramesPresented.store(0, std::memory_order_relaxed);
    gTextureUploads.store(0, std::memory_order_relaxed);
    gNormalizedTextureUploads.store(0, std::memory_order_relaxed);
    gTextureUploadErrors.store(0, std::memory_order_relaxed);
    gTextureParameterNormalizations.store(0, std::memory_order_relaxed);
    gSuspends.store(0, std::memory_order_relaxed);
    gResumes.store(0, std::memory_order_relaxed);
    gInitialized.store(true, std::memory_order_release);

    writeLineLocked("session", "------------------------------------------------------------", true);
    char message[512] = {};
    std::snprintf(
        message,
        sizeof(message),
        "session_start encounter=%s build=%s",
        gEncounter,
        gBuildIdentifier);
    writeLineLocked("session", message, true);
    writeBuildInfoFile(root);
    return true;
}

extern "C" void SeriousIOS_DiagnosticsShutdown(void) {
    SeriousIOS_DiagnosticsWriteSummary("shutdown");
    std::lock_guard<std::mutex> lock(gLogMutex);
    if (gLogFile != nullptr) {
        writeLineLocked("session", "session_end", true);
        std::fclose(gLogFile);
        gLogFile = nullptr;
    }
    gInitialized.store(false, std::memory_order_release);
}

extern "C" void SeriousIOS_DiagnosticsFlush(void) {
    std::lock_guard<std::mutex> lock(gLogMutex);
    if (gLogFile != nullptr) {
        std::fflush(gLogFile);
    }
}

extern "C" void SeriousIOS_DiagnosticsLog(
    const char* category,
    const char* format,
    ...) {
    va_list arguments;
    va_start(arguments, format);
    logFormatted(category, true, format, arguments);
    va_end(arguments);
}

extern "C" void SeriousIOS_DiagnosticsLogStage(const char* stage) {
    SeriousIOS_DiagnosticsLog(
        "stage",
        "stage=%s",
        stage == nullptr ? "unknown" : stage);
}

extern "C" void SeriousIOS_DiagnosticsRecordFramePresented(void) {
    const unsigned long long count =
        gFramesPresented.fetch_add(1, std::memory_order_relaxed) + 1;
    if (count == 1) {
        SeriousIOS_DiagnosticsLog("frame", "first_frame_presented");
    } else if ((count % kPeriodicFrameInterval) == 0) {
        SeriousIOS_DiagnosticsWriteSummary("periodic-frame-summary");
    }
}

extern "C" void SeriousIOS_DiagnosticsRecordTextureUpload(
    uint32_t requestedInternalFormat,
    uint32_t normalizedInternalFormat,
    int width,
    int height,
    int level,
    uint32_t error) {
    const unsigned long long count =
        gTextureUploads.fetch_add(1, std::memory_order_relaxed) + 1;
    if (requestedInternalFormat != normalizedInternalFormat) {
        gNormalizedTextureUploads.fetch_add(1, std::memory_order_relaxed);
    }
    if (error != 0) {
        gTextureUploadErrors.fetch_add(1, std::memory_order_relaxed);
    }

    if (count <= kDetailedTextureUploadLimit || error != 0) {
        SeriousIOS_DiagnosticsLog(
            error == 0 ? "texture" : "gl-error",
            "upload=%llu level=%d size=%dx%d requested_internal=0x%X normalized_internal=0x%X error=0x%X",
            count,
            level,
            width,
            height,
            requestedInternalFormat,
            normalizedInternalFormat,
            error);
    }
}

extern "C" void SeriousIOS_DiagnosticsRecordTextureParameterNormalization(
    uint32_t parameter,
    int requestedValue,
    int normalizedValue,
    uint32_t error) {
    const unsigned long long count =
        gTextureParameterNormalizations.fetch_add(1, std::memory_order_relaxed) + 1;
    if (count <= 16 || error != 0) {
        SeriousIOS_DiagnosticsLog(
            error == 0 ? "texture" : "gl-error",
            "parameter_normalized=%llu parameter=0x%X requested=0x%X normalized=0x%X error=0x%X",
            count,
            parameter,
            requestedValue,
            normalizedValue,
            error);
    }
}

extern "C" void SeriousIOS_DiagnosticsRecordSuspend(void) {
    const unsigned long long count = gSuspends.fetch_add(1, std::memory_order_relaxed) + 1;
    SeriousIOS_DiagnosticsLog("lifecycle", "suspend count=%llu", count);
    SeriousIOS_DiagnosticsWriteSummary("suspend");
}

extern "C" void SeriousIOS_DiagnosticsRecordResume(void) {
    const unsigned long long count = gResumes.fetch_add(1, std::memory_order_relaxed) + 1;
    SeriousIOS_DiagnosticsLog("lifecycle", "resume count=%llu", count);
}

extern "C" void SeriousIOS_DiagnosticsWriteSummary(const char* reason) {
    SeriousIOS_DiagnosticsLog(
        "summary",
        "reason=%s frames=%llu texture_uploads=%llu normalized_uploads=%llu texture_errors=%llu parameter_normalizations=%llu suspends=%llu resumes=%llu",
        reason == nullptr ? "unspecified" : reason,
        gFramesPresented.load(std::memory_order_relaxed),
        gTextureUploads.load(std::memory_order_relaxed),
        gNormalizedTextureUploads.load(std::memory_order_relaxed),
        gTextureUploadErrors.load(std::memory_order_relaxed),
        gTextureParameterNormalizations.load(std::memory_order_relaxed),
        gSuspends.load(std::memory_order_relaxed),
        gResumes.load(std::memory_order_relaxed));
}

extern "C" const char* SeriousIOS_DiagnosticsGetLogPath(void) {
    return gLogPath;
}
