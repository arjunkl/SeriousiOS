#pragma once

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*SeriousIOSPresentCallback)(void* context);
typedef int (*SeriousIOSMakeCurrentCallback)(void* context);

bool SeriousIOS_ConfigurePaths(
    const char* executablePath,
    const char* dataPath,
    const char* userPath,
    const char* cachePath,
    const char* temporaryPath);
bool SeriousIOS_ArePathsConfigured(void);
const char* SeriousIOS_GetExecutablePath(void);
const char* SeriousIOS_GetDataPath(void);
const char* SeriousIOS_GetUserPath(void);
const char* SeriousIOS_GetCachePath(void);
const char* SeriousIOS_GetTemporaryPath(void);

void SeriousIOS_SetSDLWindowSize(int width, int height);
void SeriousIOS_SetPresentCallback(
    SeriousIOSPresentCallback callback,
    void* context);
void SeriousIOS_SetGLContext(
    void* context,
    SeriousIOSMakeCurrentCallback makeCurrentCallback);
void* SeriousIOS_GetGLContext(void);
int SeriousIOS_MakeGLContextCurrent(void);

void* SeriousIOS_GetOpenGLCompatProcAddress(const char* procedure);
void* SeriousIOS_GetOpenGLTextureCompatProcAddress(const char* procedure);
bool SeriousIOS_ValidateOpenGLCompatibility(void);
const char* SeriousIOS_GetOpenGLCompatibilityError(void);

#ifdef __cplusplus
} // extern "C"
#endif
