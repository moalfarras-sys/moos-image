using MoRemote;

int passed=0;
void Eq<T>(T expected,T actual,string name){if(!EqualityComparer<T>.Default.Equals(expected,actual))throw new Exception($"{name}: expected {expected}, got {actual}");passed++;}
void Throws(Action a,string name){try{a();throw new Exception(name+": did not reject");}catch(ArgumentOutOfRangeException){passed++;}}
(double x,double y) Client(double px,double py,double left,double top,double width,double height)=>(Math.Clamp((px-left)/width,0,1),Math.Clamp((py-top)/height,0,1));

var normal=new LogicalRect(0,0,1397,786);
Eq((0,0),CoordinateMapper.NormalizedToDesktop(0,0,normal),"top-left");
Eq((1396,785),CoordinateMapper.NormalizedToDesktop(1,1,normal),"bottom-right");
Eq((698,392),CoordinateMapper.NormalizedToDesktop(.5,.5,normal),"scaled center");
var neg=new LogicalRect(-1920,-200,3840,1280);
Eq((-1920,-200),CoordinateMapper.NormalizedToDesktop(0,0,neg),"negative origin");
Eq((1919,1079),CoordinateMapper.NormalizedToDesktop(1,1,neg),"multi-monitor extent");
var portrait=Client(195,422,0,300,390,219.375);Eq((.5,Math.Clamp((422d-300)/219.375,0,1)),portrait,"portrait letterbox");
var landscape=Client(422,195,120,0,600,390);Eq((302d/600,.5),landscape,"landscape crop/content rect");
Eq((0d,1d),Client(-50,999,20,30,300,200),"out-of-content clamp");
Throws(()=>CoordinateMapper.NormalizedToDesktop(double.NaN,.5,normal),"NaN");
Throws(()=>CoordinateMapper.NormalizedToDesktop(double.PositiveInfinity,.5,normal),"infinity");
Throws(()=>CoordinateMapper.NormalizedToDesktop(.5,.5,new(0,0,0,10)),"empty geometry");
Eq((0,785),CoordinateMapper.NormalizedToDesktop(-5,9,normal),"out-of-range clamp");
var guard=new InputSequenceGuard();Eq(true,guard.Accept(1,1000,1000,out _),"sequence first");Eq(false,guard.Accept(1,1001,1001,out _),"sequence duplicate");Eq(false,guard.Accept(0,1002,1002,out _),"sequence reordered");Eq(false,new InputSequenceGuard().Accept(1,0,40000,out _),"stale event");

var unicode="مرحباً Grüße English";Eq(unicode,System.Text.Encoding.UTF8.GetString(System.Text.Encoding.UTF8.GetBytes(unicode)),"clipboard unicode");
Console.WriteLine($"PASS: {passed} mapping/validation/Unicode tests");
