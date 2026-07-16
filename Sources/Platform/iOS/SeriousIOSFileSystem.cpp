#include "SeriousIOSPlatformBridge.h"

#include <Engine/Engine.h>
#include <Engine/Base/FileSystem.h>

#include <cstdio>
#include <cstring>
#include <dirent.h>
#include <sys/stat.h>

ENGINE_API CFileSystem* _pFileSystem = nullptr;

namespace {

void copyPath(char* destination, ULONG destinationSize, const char* source) {
    if (destination == nullptr || destinationSize == 0) {
        return;
    }
    std::snprintf(
        destination,
        static_cast<std::size_t>(destinationSize),
        "%s",
        source == nullptr ? "" : source);
    destination[destinationSize - 1] = '\0';
}

class SeriousIOSFileSystem final : public CFileSystem {
public:
    SeriousIOSFileSystem(const char* executablePath, const char* gameName) {
        (void)gameName;
        configuredExecutable_ = SeriousIOS_GetExecutablePath();
        configuredUser_ = SeriousIOS_GetUserPath();
        if (configuredExecutable_ == nullptr || *configuredExecutable_ == '\0') {
            configuredExecutable_ = executablePath == nullptr ? "" : executablePath;
        }
        if (configuredUser_ == nullptr) {
            configuredUser_ = "";
        }
    }

    void GetExecutablePath(char* buffer, ULONG bufferSize) override {
        copyPath(buffer, bufferSize, configuredExecutable_);
    }

    void GetUserDirectory(char* buffer, ULONG bufferSize) override {
        copyPath(buffer, bufferSize, configuredUser_);
    }

    CDynamicArray<CTString>* FindFiles(
        const char* directory,
        const char* wildcard) override {
        auto* result = new CDynamicArray<CTString>;
        DIR* handle = opendir(directory);
        if (handle == nullptr) {
            return result;
        }

        while (dirent* entry = readdir(handle)) {
            CTString name(entry->d_name);
            if (name.Matches(wildcard)) {
                *result->New() = name;
            }
        }
        closedir(handle);
        return result;
    }

private:
    const char* configuredExecutable_;
    const char* configuredUser_;
};

} // namespace

CFileSystem* CFileSystem::GetInstance(const char* argv0, const char* gameName) {
    return new SeriousIOSFileSystem(argv0, gameName);
}

const char* CFileSystem::GetDirSeparator(void) {
    return "/";
}

BOOL CFileSystem::IsDummyFile(const char* filename) {
    return filename != nullptr
        && (std::strcmp(filename, ".") == 0 || std::strcmp(filename, "..") == 0);
}

BOOL CFileSystem::Exists(const char* filename) {
    struct stat status = {};
    return filename != nullptr && stat(filename, &status) == 0;
}

BOOL CFileSystem::IsDirectory(const char* filename) {
    struct stat status = {};
    return filename != nullptr
        && stat(filename, &status) == 0
        && S_ISDIR(status.st_mode);
}
