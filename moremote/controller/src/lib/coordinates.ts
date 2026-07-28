export interface ContentRect {left:number;top:number;width:number;height:number}
export function normalizeContentPoint(clientX:number,clientY:number,rect:ContentRect){
 if(![clientX,clientY,rect.left,rect.top,rect.width,rect.height].every(Number.isFinite)||rect.width<=0||rect.height<=0)throw new RangeError("invalid content geometry");
 return {x:Math.min(1,Math.max(0,(clientX-rect.left)/rect.width)),y:Math.min(1,Math.max(0,(clientY-rect.top)/rect.height))};
}

/**
 * The same mapping, but for a picture that is drawn TURNED A QUARTER TURN on screen.
 *
 * WHY A ROTATED VIEW EXISTS AT ALL
 *
 * A 16:9 desktop fitted into a 9:19.5 phone held upright uses a quarter of the display. That is not
 * an estimate: measured on this controller at 390x844, the picture occupied rows 312..528 of 844 —
 * 25.6% lit, 74.4% black. The app's answer was a toast asking the user to turn the phone sideways,
 * which is advice rather than a fix, and it is ignored in a browser tab (no orientation lock) and on
 * iOS entirely.
 *
 * Turning the PICTURE instead of asking the user to turn the PHONE gives the same desktop the whole
 * display, upright, the moment they tilt their hand — and costs nothing when they do rotate, because
 * the rotation switches itself off as soon as the viewport is landscape.
 *
 * THE GEOMETRY
 *
 * `rect` is the on-screen box the picture occupies, exactly as in the unrotated case — so
 * letterboxing, panning, zooming and hit-testing all keep working on a plain axis-aligned rectangle
 * and only this one function knows about the turn.
 *
 * The picture is drawn rotated a quarter turn ANTICLOCKWISE, which is what makes tilting the phone
 * CLOCKWISE (the instinctive direction, and the one that produces landscape-primary on essentially
 * every handset) bring the desktop upright. So the desktop's "up" points at the screen's left edge:
 *
 *     source x (0 -> 1)  runs UP the screen      => nx = 1 - (y - top) / height
 *     source y (0 -> 1)  runs RIGHT across it    => ny =     (x - left) / width
 */
export function normalizeRotatedPoint(clientX:number,clientY:number,rect:ContentRect){
 if(![clientX,clientY,rect.left,rect.top,rect.width,rect.height].every(Number.isFinite)||rect.width<=0||rect.height<=0)throw new RangeError("invalid content geometry");
 const clamp=(v:number)=>Math.min(1,Math.max(0,v));
 return {x:clamp(1-(clientY-rect.top)/rect.height),y:clamp((clientX-rect.left)/rect.width)};
}

/** Where a normalized source point lands on screen — the exact inverse of the two above. */
export function projectPoint(nx:number,ny:number,rect:ContentRect,rotated:boolean){
 return rotated
  ? {x:rect.left+ny*rect.width, y:rect.top+(1-nx)*rect.height}
  : {x:rect.left+nx*rect.width, y:rect.top+ny*rect.height};
}

/**
 * A movement expressed in SCREEN pixels, re-expressed in the picture's own axes.
 *
 * Anything that reads a finger delta and means it as a movement ACROSS THE DESKTOP has to go
 * through here: a swipe toward the top of a rotated phone is a swipe toward the right-hand side of
 * the desktop, and a scroll that ignores that scrolls the wrong axis. (Panning is the exception and
 * deliberately does not use this — panning moves the drawn box itself, which lives in screen space
 * and should follow the finger literally.)
 */
export function rotateDelta(dx:number,dy:number,rotated:boolean){
 return rotated?{dx:-dy,dy:dx}:{dx,dy};
}
