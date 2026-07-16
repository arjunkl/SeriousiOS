#pragma once

#include <stdbool.h>

#ifdef __cplusplus
extern "C" {
#endif

bool SeriousIOS_ApplicationInitialize(void);
bool SeriousIOS_ApplicationFrame(void);
void SeriousIOS_ApplicationSuspend(void);
void SeriousIOS_ApplicationResume(void);
void SeriousIOS_ApplicationShutdown(void);
bool SeriousIOS_ApplicationIsInitialized(void);
const char* SeriousIOS_ApplicationGetError(void);

// Called by the transformed upstream application startup path before each
// substantial initialization phase. Every stage is flushed to persistent app
// support storage so an abort, signal, or hard crash still leaves a useful
// breadcrumb for the next launch.
void SeriousIOS_ApplicationSetStage(const char* stage);
const char* SeriousIOS_ApplicationGetStage(void);

#ifdef __cplusplus
} // extern "C"
#endif
