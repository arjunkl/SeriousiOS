#!/usr/bin/env python3
"""Inject native UIKit touch routing into the generated SeriousiOS host."""

from __future__ import annotations

import argparse
from pathlib import Path


TOUCH_METHODS = r'''- (void)routeMenuTouch:(UITouch*)touch activate:(BOOL)activate {
    if (touch == nil || _drawableWidth <= 0 || _drawableHeight <= 0) {
        return;
    }

    const CGRect bounds = self.bounds;
    if (CGRectGetWidth(bounds) <= 0.0 || CGRectGetHeight(bounds) <= 0.0) {
        return;
    }

    const CGPoint point = [touch locationInView:self];
    const CGFloat normalizedX = point.x / CGRectGetWidth(bounds);
    const CGFloat normalizedY = point.y / CGRectGetHeight(bounds);
    const int pixelX = (int)(normalizedX * (CGFloat)(_drawableWidth - 1) + 0.5);
    const int pixelY = (int)(normalizedY * (CGFloat)(_drawableHeight - 1) + 0.5);

    if (activate) {
        SeriousIOS_ApplicationMenuPointerActivate(pixelX, pixelY);
    } else {
        SeriousIOS_ApplicationMenuPointerMove(pixelX, pixelY);
    }
}

- (void)touchesBegan:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    [self routeMenuTouch:touches.anyObject activate:NO];
}

- (void)touchesMoved:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    [self routeMenuTouch:touches.anyObject activate:NO];
}

- (void)touchesEnded:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)event;
    [self routeMenuTouch:touches.anyObject activate:YES];
}

- (void)touchesCancelled:(NSSet<UITouch*>*)touches withEvent:(UIEvent*)event {
    (void)touches;
    (void)event;
}
'''


def transform(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    marker = "- (void)destroyDrawable {"
    count = text.count(marker)
    if count != 1:
        raise RuntimeError(
            f"expected one destroyDrawable insertion point, found {count}"
        )
    if "SeriousIOS_ApplicationMenuPointerActivate" in text:
        raise RuntimeError("menu touch routing is already present")
    path.write_text(
        text.replace(marker, TOUCH_METHODS + "\n" + marker, 1),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("host_source", type=Path)
    args = parser.parse_args()
    source = args.host_source.resolve()
    if not source.is_file():
        raise SystemExit(f"host source does not exist: {source}")
    transform(source)
    print(f"Injected native menu touch routing into {source}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
