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

#ifdef __cplusplus
} // extern "C"
#endif
