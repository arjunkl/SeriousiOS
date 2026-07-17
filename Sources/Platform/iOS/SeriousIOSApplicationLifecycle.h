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

// Feed UIKit touch coordinates, already converted into native drawable pixels,
// into Serious Sam's existing menu mouse path. Moving updates the highlighted
// gadget; activating performs the ordinary left-button action on that gadget.
bool SeriousIOS_ApplicationMenuPointerMove(int pixelX, int pixelY);
bool SeriousIOS_ApplicationMenuPointerActivate(int pixelX, int pixelY);

// Called by the transformed upstream application startup path before each
// substantial initialization phase. Every stage is flushed to persistent app
// support storage so an abort, signal, or hard crash still leaves a useful
// breadcrumb for the next launch.
void SeriousIOS_ApplicationSetStage(const char* stage);
const char* SeriousIOS_ApplicationGetStage(void);

// Called from the iOS ErrorReporting transform after the legacy FatalError
// message has been formatted but before it terminates the process.
void SeriousIOS_ApplicationRecordFatalError(const char* message);

#ifdef __cplusplus
} // extern "C"
#endif
