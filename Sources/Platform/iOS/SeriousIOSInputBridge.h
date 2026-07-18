#pragma once

#include <array>
#include <cstddef>
#include <cstdint>
#include <mutex>

namespace seriousios {

constexpr std::size_t kMaximumActions = 64;

struct InputSnapshot {
    float moveForward = 0.0f;
    float moveRight = 0.0f;
    float lookYawDelta = 0.0f;
    float lookPitchDelta = 0.0f;
    std::array<bool, kMaximumActions> heldActions{};
    std::array<bool, kMaximumActions> pressedActions{};
};

class InputBridge final {
public:
    void setMovement(float forward, float right) noexcept;
    void addLookDelta(float yaw, float pitch) noexcept;
    void setAction(std::size_t action, bool pressed) noexcept;
    void pulseAction(std::size_t action) noexcept;
    void releaseAll() noexcept;
    [[nodiscard]] InputSnapshot snapshot() noexcept;
    [[nodiscard]] InputSnapshot consume() noexcept;

private:
    static float clampAxis(float value) noexcept;
    InputSnapshot snapshotLocked() const noexcept;

    std::mutex mutex_;
    float moveForward_ = 0.0f;
    float moveRight_ = 0.0f;
    float lookYawDelta_ = 0.0f;
    float lookPitchDelta_ = 0.0f;
    std::array<bool, kMaximumActions> heldActions_{};
    std::array<bool, kMaximumActions> pressedActions_{};
};

} // namespace seriousios
