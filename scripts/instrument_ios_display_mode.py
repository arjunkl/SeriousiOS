#!/usr/bin/env python3
"""Add durable iOS checkpoints around Serious Sam's display-mode transition."""

from __future__ import annotations

import argparse
from pathlib import Path

ENCOUNTERS = ("TFE", "TSE")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly one match, found {count}")
    return text.replace(old, new, 1)


def instrument(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    replacements = (
        (
            '''  // destroy canvas if existing
  _pGame->DisableLoadingHook();''',
            '''  // destroy canvas if existing
  SERIOUSIOS_STAGE("display-disable-loading-hook");
  _pGame->DisableLoadingHook();''',
            "disable loading hook",
        ),
        (
            '''  if( pvpViewPort!=NULL) {
    _pGfx->DestroyWindowCanvas( pvpViewPort);''',
            '''  if( pvpViewPort!=NULL) {
    SERIOUSIOS_STAGE("display-destroy-old-canvas");
    _pGfx->DestroyWindowCanvas( pvpViewPort);''',
            "destroy old canvas",
        ),
        (
            '''  // close the application window
  CloseMainWindow();

  // try to set new display mode''',
            '''  // close the application window
  SERIOUSIOS_STAGE("display-detach-legacy-window");
  CloseMainWindow();

  // try to set new display mode''',
            "detach legacy window",
        ),
        (
            '''  // TODO: enable full screen
  if( bFullScreenMode) {''',
            '''  // TODO: enable full screen
  SERIOUSIOS_STAGE("display-driver-mode-transition");
  if( bFullScreenMode) {''',
            "driver mode transition",
        ),
        (
            '''    bSuccess = _pGfx->SetDisplayMode( eGfxAPI, iAdapter, pixSizeI, pixSizeJ, eColorDepth);
    if( bSuccess && eGfxAPI==GAT_OGL) OpenMainWindowFullScreen( pixSizeI, pixSizeJ);''',
            '''    SERIOUSIOS_STAGE("display-set-fullscreen-mode");
    bSuccess = _pGfx->SetDisplayMode( eGfxAPI, iAdapter, pixSizeI, pixSizeJ, eColorDepth);
    if( bSuccess && eGfxAPI==GAT_OGL) {
      SERIOUSIOS_STAGE("display-reattach-fullscreen-window");
      OpenMainWindowFullScreen( pixSizeI, pixSizeJ);
    }''',
            "fullscreen transition",
        ),
        (
            '''    bSuccess = _pGfx->ResetDisplayMode( eGfxAPI);
    if( bSuccess && eGfxAPI==GAT_OGL) OpenMainWindowNormal( pixSizeI, pixSizeJ);''',
            '''    SERIOUSIOS_STAGE("display-reset-windowed-mode");
    bSuccess = _pGfx->ResetDisplayMode( eGfxAPI);
    if( bSuccess && eGfxAPI==GAT_OGL) {
      SERIOUSIOS_STAGE("display-reattach-windowed-window");
      OpenMainWindowNormal( pixSizeI, pixSizeJ);
    }''',
            "windowed transition",
        ),
        (
            '''    // create canvas
    ASSERT( pvpViewPort==NULL);
    ASSERT( pdpNormal==NULL);
    _pGfx->CreateWindowCanvas( _hwndMain, &pvpViewPort, &pdpNormal);''',
            '''    // create canvas
    ASSERT( pvpViewPort==NULL);
    ASSERT( pdpNormal==NULL);
    SERIOUSIOS_STAGE("display-create-window-canvas");
    _pGfx->CreateWindowCanvas( _hwndMain, &pvpViewPort, &pdpNormal);
    SERIOUSIOS_STAGE("display-window-canvas-created");''',
            "create window canvas",
        ),
        (
            '''    pdp = pdpNormal;
    if( pdp!=NULL && pdp->Lock()) {
      pdp->Fill(C_BLACK|CT_OPAQUE);''',
            '''    pdp = pdpNormal;
    SERIOUSIOS_STAGE("display-first-clear-lock");
    if( pdp!=NULL && pdp->Lock()) {
      SERIOUSIOS_STAGE("display-first-clear-fill");
      pdp->Fill(C_BLACK|CT_OPAQUE);''',
            "first clear lock",
        ),
        (
            '''      pdp->Unlock();
      pvpViewPort->SwapBuffers();
      pdp->Lock();
      pdp->Fill(C_BLACK|CT_OPAQUE);
      pdp->Unlock();
      pvpViewPort->SwapBuffers();''',
            '''      pdp->Unlock();
      SERIOUSIOS_STAGE("display-first-clear-swap");
      pvpViewPort->SwapBuffers();
      SERIOUSIOS_STAGE("display-second-clear-lock");
      pdp->Lock();
      SERIOUSIOS_STAGE("display-second-clear-fill");
      pdp->Fill(C_BLACK|CT_OPAQUE);
      pdp->Unlock();
      SERIOUSIOS_STAGE("display-second-clear-swap");
      pvpViewPort->SwapBuffers();''',
            "double clear and swap",
        ),
        (
            '''    pdpWideScreen = new CDrawPort( pdp, PIXaabbox2D( PIX2D(0,pixYBegAdj), PIX2D(pixXEnd, pixYEndAdj)));''',
            '''    SERIOUSIOS_STAGE("display-create-wide-drawport");
    pdpWideScreen = new CDrawPort( pdp, PIXaabbox2D( PIX2D(0,pixYBegAdj), PIX2D(pixXEnd, pixYEndAdj)));''',
            "wide drawport",
        ),
        (
            '''    BOOL bSuccess = FALSE;
    if( pdp!=NULL && pdp->Lock()) {
      pdp->Fill(_pGame->LCDGetColor(C_dGREEN|CT_OPAQUE, "bcg fill"));''',
            '''    BOOL bSuccess = FALSE;
    SERIOUSIOS_STAGE("display-context-validation-lock");
    if( pdp!=NULL && pdp->Lock()) {
      SERIOUSIOS_STAGE("display-context-validation-fill");
      pdp->Fill(_pGame->LCDGetColor(C_dGREEN|CT_OPAQUE, "bcg fill"));''',
            "context validation lock",
        ),
        (
            '''      pdp->Unlock();
      pvpViewPort->SwapBuffers();
      bSuccess = TRUE;
    }
    _pGame->EnableLoadingHook(pdp);''',
            '''      pdp->Unlock();
      SERIOUSIOS_STAGE("display-context-validation-swap");
      pvpViewPort->SwapBuffers();
      bSuccess = TRUE;
    }
    SERIOUSIOS_STAGE("display-enable-loading-hook");
    _pGame->EnableLoadingHook(pdp);''',
            "context validation swap",
        ),
        (
            '''    // if the mode is not working, or is not accelerated
    if( !bSuccess || !_pGfx->IsCurrentModeAccelerated())''',
            '''    // if the mode is not working, or is not accelerated
    SERIOUSIOS_STAGE("display-acceleration-check");
    if( !bSuccess || !_pGfx->IsCurrentModeAccelerated())''',
            "acceleration check",
        ),
        (
            '''  // apply 3D-acc settings
  ApplyGLSettings(FALSE);''',
            '''  // apply 3D-acc settings
  SERIOUSIOS_STAGE("display-apply-gl-settings");
  ApplyGLSettings(FALSE);
  SERIOUSIOS_STAGE("display-mode-complete");''',
            "apply GL settings",
        ),
    )

    for old, new, label in replacements:
        text = replace_once(text, old, new, f"{path}: {label}")

    path.write_text(text, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("upstream", type=Path)
    args = parser.parse_args()
    upstream = args.upstream.resolve()

    for encounter in ENCOUNTERS:
        source = upstream / f"Sam{encounter}" / "Sources/SeriousSam/SeriousSam.cpp"
        if not source.is_file():
            raise FileNotFoundError(source)
        instrument(source)
        print(f"Instrumented iOS display transition in {source.relative_to(upstream)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
