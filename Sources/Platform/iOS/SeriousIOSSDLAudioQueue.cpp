#include "SeriousIOSDiagnostics.h"

#include <SDL.h>

#include <AudioToolbox/AudioQueue.h>

#include <array>
#include <atomic>
#include <cstdint>
#include <cstring>
#include <memory>
#include <mutex>
#include <unordered_map>

namespace {

constexpr std::size_t kAudioBufferCount = 3;
const char* kAudioDriverName = "coreaudio-audioqueue";
const char* kAudioDeviceName = "iPhone Audio Output";

struct AudioDeviceState {
    SDL_AudioSpec specification = {};
    AudioStreamBasicDescription streamFormat = {};
    AudioQueueRef queue = nullptr;
    std::array<AudioQueueBufferRef, kAudioBufferCount> buffers = {};
    std::atomic<bool> paused{true};
    std::atomic<bool> closing{false};
    std::atomic<bool> started{false};
    std::atomic<bool> enqueueErrorLogged{false};
    std::recursive_mutex callbackMutex;
};

std::atomic<SDL_AudioDeviceID> gNextAudioDeviceID{1};
std::mutex gAudioDeviceMutex;
std::unordered_map<SDL_AudioDeviceID, std::shared_ptr<AudioDeviceState>> gAudioDevices;

std::shared_ptr<AudioDeviceState> audioDevice(SDL_AudioDeviceID device) {
    std::lock_guard<std::mutex> lock(gAudioDeviceMutex);
    const auto iterator = gAudioDevices.find(device);
    return iterator == gAudioDevices.end() ? nullptr : iterator->second;
}

bool configureStreamFormat(
    const SDL_AudioSpec& specification,
    AudioStreamBasicDescription& format) {
    const int bitsPerChannel = SDL_AUDIO_BITSIZE(specification.format);
    if (specification.freq <= 0
        || specification.channels == 0
        || bitsPerChannel <= 0
        || bitsPerChannel % 8 != 0) {
        return false;
    }

    const UInt32 bytesPerSample = static_cast<UInt32>(bitsPerChannel / 8);
    const UInt32 bytesPerFrame =
        bytesPerSample * static_cast<UInt32>(specification.channels);

    format = {};
    format.mSampleRate = static_cast<Float64>(specification.freq);
    format.mFormatID = kAudioFormatLinearPCM;
    format.mFormatFlags = kAudioFormatFlagIsPacked;
    if (SDL_AUDIO_ISFLOAT(specification.format)) {
        format.mFormatFlags |= kAudioFormatFlagIsFloat;
    } else if (SDL_AUDIO_ISSIGNED(specification.format)) {
        format.mFormatFlags |= kAudioFormatFlagIsSignedInteger;
    }
    if (SDL_AUDIO_ISBIGENDIAN(specification.format)) {
        format.mFormatFlags |= kAudioFormatFlagIsBigEndian;
    }
    format.mBytesPerPacket = bytesPerFrame;
    format.mFramesPerPacket = 1;
    format.mBytesPerFrame = bytesPerFrame;
    format.mChannelsPerFrame = specification.channels;
    format.mBitsPerChannel = static_cast<UInt32>(bitsPerChannel);
    return true;
}

void fillAudioBuffer(AudioDeviceState& state, AudioQueueBufferRef buffer) {
    if (buffer == nullptr || buffer->mAudioData == nullptr) {
        return;
    }

    const UInt32 requestedBytes = state.specification.size;
    std::memset(
        buffer->mAudioData,
        state.specification.silence,
        static_cast<std::size_t>(requestedBytes));

    if (!state.paused.load(std::memory_order_acquire)
        && state.specification.callback != nullptr) {
        std::lock_guard<std::recursive_mutex> lock(state.callbackMutex);
        state.specification.callback(
            state.specification.userdata,
            static_cast<Uint8*>(buffer->mAudioData),
            static_cast<int>(requestedBytes));
    }
    buffer->mAudioDataByteSize = requestedBytes;
}

void audioQueueOutputCallback(
    void* userData,
    AudioQueueRef queue,
    AudioQueueBufferRef buffer) {
    AudioDeviceState* state = static_cast<AudioDeviceState*>(userData);
    if (state == nullptr || state->closing.load(std::memory_order_acquire)) {
        return;
    }

    fillAudioBuffer(*state, buffer);
    if (state->closing.load(std::memory_order_acquire)) {
        return;
    }

    const OSStatus status = AudioQueueEnqueueBuffer(queue, buffer, 0, nullptr);
    if (status != noErr && !state->enqueueErrorLogged.exchange(true)) {
        SeriousIOS_DiagnosticsLog(
            "audio",
            "audio_queue_enqueue_failed status=%d",
            static_cast<int>(status));
    }
}

void disposeAudioQueue(AudioDeviceState& state) {
    state.closing.store(true, std::memory_order_release);
    if (state.queue == nullptr) {
        return;
    }
    AudioQueueStop(state.queue, true);
    AudioQueueDispose(state.queue, true);
    state.queue = nullptr;
    state.buffers.fill(nullptr);
}

} // namespace

extern "C" {

int SDLCALL SDL_GetNumAudioDevices(int capture) {
    return capture == 0 ? 1 : 0;
}

const char* SDLCALL SDL_GetAudioDeviceName(int index, int capture) {
    return capture == 0 && index == 0 ? kAudioDeviceName : nullptr;
}

const char* SDLCALL SDL_GetCurrentAudioDriver(void) {
    return kAudioDriverName;
}

SDL_AudioDeviceID SDLCALL SDL_OpenAudioDevice(
    const char* device,
    int capture,
    const SDL_AudioSpec* desired,
    SDL_AudioSpec* obtained,
    int allowedChanges) {
    (void)device;
    (void)allowedChanges;
    if (capture != 0 || desired == nullptr) {
        return 0;
    }

    auto state = std::make_shared<AudioDeviceState>();
    state->specification = *desired;
    if (state->specification.samples == 0) {
        state->specification.samples = 2048;
    }

    const int bytesPerSample = SDL_AUDIO_BITSIZE(state->specification.format) / 8;
    if (bytesPerSample <= 0
        || !configureStreamFormat(state->specification, state->streamFormat)) {
        SeriousIOS_DiagnosticsLog(
            "audio",
            "audio_queue_format_rejected freq=%d channels=%u format=0x%04X samples=%u",
            state->specification.freq,
            static_cast<unsigned int>(state->specification.channels),
            static_cast<unsigned int>(state->specification.format),
            static_cast<unsigned int>(state->specification.samples));
        return 0;
    }

    state->specification.silence =
        state->specification.format == AUDIO_U8 ? 0x80 : 0;
    state->specification.size =
        static_cast<Uint32>(state->specification.samples)
        * state->specification.channels
        * static_cast<Uint32>(bytesPerSample);

    OSStatus status = AudioQueueNewOutput(
        &state->streamFormat,
        audioQueueOutputCallback,
        state.get(),
        nullptr,
        nullptr,
        0,
        &state->queue);
    if (status != noErr || state->queue == nullptr) {
        SeriousIOS_DiagnosticsLog(
            "audio",
            "audio_queue_create_failed status=%d",
            static_cast<int>(status));
        return 0;
    }

    AudioQueueSetParameter(state->queue, kAudioQueueParam_Volume, 1.0f);
    for (std::size_t index = 0; index < state->buffers.size(); ++index) {
        status = AudioQueueAllocateBuffer(
            state->queue,
            state->specification.size,
            &state->buffers[index]);
        if (status != noErr || state->buffers[index] == nullptr) {
            SeriousIOS_DiagnosticsLog(
                "audio",
                "audio_queue_allocate_failed index=%lu status=%d bytes=%u",
                static_cast<unsigned long>(index),
                static_cast<int>(status),
                static_cast<unsigned int>(state->specification.size));
            disposeAudioQueue(*state);
            return 0;
        }
        fillAudioBuffer(*state, state->buffers[index]);
        status = AudioQueueEnqueueBuffer(
            state->queue,
            state->buffers[index],
            0,
            nullptr);
        if (status != noErr) {
            SeriousIOS_DiagnosticsLog(
                "audio",
                "audio_queue_prime_failed index=%lu status=%d",
                static_cast<unsigned long>(index),
                static_cast<int>(status));
            disposeAudioQueue(*state);
            return 0;
        }
    }

    const SDL_AudioDeviceID deviceID =
        gNextAudioDeviceID.fetch_add(1, std::memory_order_relaxed);
    {
        std::lock_guard<std::mutex> lock(gAudioDeviceMutex);
        gAudioDevices.emplace(deviceID, state);
    }
    if (obtained != nullptr) {
        *obtained = state->specification;
    }

    SeriousIOS_DiagnosticsLog(
        "audio",
        "audio_queue_opened device=%u freq=%d channels=%u format=0x%04X samples=%u bytes=%u buffers=%lu",
        static_cast<unsigned int>(deviceID),
        state->specification.freq,
        static_cast<unsigned int>(state->specification.channels),
        static_cast<unsigned int>(state->specification.format),
        static_cast<unsigned int>(state->specification.samples),
        static_cast<unsigned int>(state->specification.size),
        static_cast<unsigned long>(state->buffers.size()));
    return deviceID;
}

void SDLCALL SDL_PauseAudioDevice(SDL_AudioDeviceID device, int pauseOn) {
    const auto state = audioDevice(device);
    if (state == nullptr || state->queue == nullptr) {
        return;
    }

    const bool paused = pauseOn != 0;
    state->paused.store(paused, std::memory_order_release);
    OSStatus status = noErr;
    if (paused) {
        if (state->started.load(std::memory_order_acquire)) {
            status = AudioQueuePause(state->queue);
        }
    } else {
        status = AudioQueueStart(state->queue, nullptr);
        if (status == noErr) {
            state->started.store(true, std::memory_order_release);
        }
    }
    SeriousIOS_DiagnosticsLog(
        "audio",
        "audio_queue_pause device=%u paused=%d status=%d",
        static_cast<unsigned int>(device),
        paused ? 1 : 0,
        static_cast<int>(status));
}

void SDLCALL SDL_CloseAudioDevice(SDL_AudioDeviceID device) {
    std::shared_ptr<AudioDeviceState> state;
    {
        std::lock_guard<std::mutex> lock(gAudioDeviceMutex);
        const auto iterator = gAudioDevices.find(device);
        if (iterator == gAudioDevices.end()) {
            return;
        }
        state = iterator->second;
        gAudioDevices.erase(iterator);
    }

    disposeAudioQueue(*state);
    SeriousIOS_DiagnosticsLog(
        "audio",
        "audio_queue_closed device=%u",
        static_cast<unsigned int>(device));
}

void SDLCALL SDL_LockAudioDevice(SDL_AudioDeviceID device) {
    const auto state = audioDevice(device);
    if (state != nullptr) {
        state->callbackMutex.lock();
    }
}

void SDLCALL SDL_UnlockAudioDevice(SDL_AudioDeviceID device) {
    const auto state = audioDevice(device);
    if (state != nullptr) {
        state->callbackMutex.unlock();
    }
}

} // extern "C"
