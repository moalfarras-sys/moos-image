export interface ContentRect { left:number;top:number;width:number;height:number }
export function normalizeContentPoint(clientX:number,clientY:number,rect:ContentRect){
 if(![clientX,clientY,rect.left,rect.top,rect.width,rect.height].every(Number.isFinite)||rect.width<=0||rect.height<=0)throw new RangeError("invalid content geometry");
 return {x:Math.min(1,Math.max(0,(clientX-rect.left)/rect.width)),y:Math.min(1,Math.max(0,(clientY-rect.top)/rect.height))};
}
