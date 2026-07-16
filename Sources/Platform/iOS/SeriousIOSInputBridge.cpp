#include "SeriousIOSInputBridge.h"

#include <algorithm>

namespace seriousios {

float InputBridge::clampAxis(float value) noexcept {
    return std::clamp(value, -1.0f, 1.0f);
}

void InputBridge::setMovement(float forward, float right) noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    moveForward_ = clampAxis(forward);
    moveRight_ = clampAxis(right);
}

void InputBridge::addLookDelta(float yaw, float pitch) noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    lookYawDelta_ += yaw;
    lookPitchDelta_ += pitch;
}

void InputBridge::setAction(std::size_t action, bool pressed) noexcept {
    if (action >= kMaximumActions) {
        return;
    }

    std::lock_guard<std::mutex> lock(mutex_);
    if (pressed && !heldActions_[action]) {
        pressedActions_[action] = true;
    }
    heldActions_[action] = pressed;
}

void InputBridge::pulseAction(std::size_t action) noexcept {
    if (action >= kMaximumActions) {
        return;
    }

    std::lock_guard<std::mutex> lock(mutex_);
    pressedActions_[action] = true;
}

void InputBridge::releaseAll() noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    moveForward_ = 0.0f;
    moveRight_ = 0.0f;
    lookYawDelta_ = 0.0f;
    lookPitchDelta_ = 0.0f;
    heldActions_.fill(false);
    pressedActions_.fill(false);
}

InputSnapshot InputBridge::consume() noexcept {
    std::lock_guard<std::mutex> lock(mutex_);

    InputSnapshot snapshot;
    snapshot.moveForward = moveForward_;
    snapshot.moveRight = moveRight_;
    snapshot.lookYawDelta = lookYawDelta_;
    snapshot.lookPitchDelta = lookPitchDelta_;
    snapshot.heldActions = heldActions_;
    snapshot.pressedActions = pressedActions_;

    lookYawDelta_ = 0.0f;
    lookPitchDelta_ = 0.0f;
    pressedActions_.fill(false);
    return snapshot;
}

} // namespace seriousios
