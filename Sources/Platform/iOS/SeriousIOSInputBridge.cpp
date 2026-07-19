#include "SeriousIOSInputBridge.h"

namespace seriousios {

float InputBridge::clampAxis(float value) noexcept {
    if (value < -1.0f) {
        return -1.0f;
    }
    if (value > 1.0f) {
        return 1.0f;
    }
    return value;
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

InputSnapshot InputBridge::snapshotLocked() const noexcept {
    InputSnapshot result;
    result.moveForward = moveForward_;
    result.moveRight = moveRight_;
    result.lookYawDelta = lookYawDelta_;
    result.lookPitchDelta = lookPitchDelta_;
    result.heldActions = heldActions_;
    result.pressedActions = pressedActions_;
    return result;
}

InputSnapshot InputBridge::snapshot() noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    return snapshotLocked();
}

InputSnapshot InputBridge::consume() noexcept {
    std::lock_guard<std::mutex> lock(mutex_);
    InputSnapshot result = snapshotLocked();
    lookYawDelta_ = 0.0f;
    lookPitchDelta_ = 0.0f;
    pressedActions_.fill(false);
    return result;
}

} // namespace seriousios
