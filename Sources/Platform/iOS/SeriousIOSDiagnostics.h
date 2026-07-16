#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

bool SeriousIOS_DiagnosticsInitialize(
    const char* encounter,
    const char* buildIdentifier);
void SeriousIOS_DiagnosticsShutdown(void);
void SeriousIOS_DiagnosticsFlush(void);
void SeriousIOS_DiagnosticsLog(
    const char* category,
    const char* format,
    ...);
void SeriousIOS_DiagnosticsLogStage(const char* stage);
void SeriousIOS_DiagnosticsRecordFramePresented(void);
void SeriousIOS_DiagnosticsRecordTextureUpload(
    uint32_t requestedInternalFormat,
    uint32_t normalizedInternalFormat,
    int width,
    int height,
    int level,
    uint32_t error);
void SeriousIOS_DiagnosticsRecordTextureParameterNormalization(
    uint32_t parameter,
    int requestedValue,
    int normalizedValue,
    uint32_t error);
void SeriousIOS_DiagnosticsRecordSuspend(void);
void SeriousIOS_DiagnosticsRecordResume(void);
void SeriousIOS_DiagnosticsWriteSummary(const char* reason);
const char* SeriousIOS_DiagnosticsGetLogPath(void);

#ifdef __cplusplus
} // extern "C"
#endif
