#pragma once

#ifdef __cplusplus
extern "C" {
#endif

typedef void (*SeriousIOSPresentCallback)(void* context);

void SeriousIOS_SetSDLWindowSize(int width, int height);
void SeriousIOS_SetPresentCallback(
    SeriousIOSPresentCallback callback,
    void* context);

#ifdef __cplusplus
} // extern "C"
#endif
