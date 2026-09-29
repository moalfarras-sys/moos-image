from pathlib import Path
import json
import numpy as np
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler
import flatbuffers, tflite

ROOT=Path(__file__).parent
rng=np.random.default_rng(109)
manifest=json.loads((ROOT/'manifest.json').read_text())
pos=[];neg=[];hold=[];hold_y=[]
for entry in manifest:
 f=np.fromfile(ROOT/'clips'/(entry['file']+'.features'),dtype='<f4').reshape(-1,96)
 windows=np.array([f[j-16:j].reshape(-1) for j in range(16,len(f)+1)],dtype=np.float32)
 if not len(windows):continue
 if entry['label']:
  # Each embedding contains 760ms of audio; the classifier spans another 1.2s.
  end=int(round((1+entry['duration']+.25-.76)/.08))
  indices=np.clip(np.array([end-2,end,end+2])-16,0,len(windows)-1)
  selected=windows[indices]
 else:selected=windows[::3]
 idx=int(entry['file'].split('-')[1])
 if idx%5==0:
  hold.extend(selected);hold_y.extend([entry['label']]*len(selected))
 else:(pos if entry['label'] else neg).extend(selected)
background=np.load(ROOT/'negative-validation.npy',mmap_mode='r')
split=int(len(background)*.8)
for j in rng.integers(16,split,size=6000):neg.append(background[j-16:j].reshape(-1))
negative_test=np.array([background[j-16:j].reshape(-1) for j in range(split+16,len(background),16)])
pos=np.array(pos);neg=np.array(neg)
X=np.concatenate([np.tile(pos,(max(1,len(neg)//len(pos)),1)),neg])
y=np.concatenate([np.ones(len(X)-len(neg)),np.zeros(len(neg))])
order=rng.permutation(len(X));X=X[order];y=y[order]
scale=StandardScaler().fit(X)
model=MLPClassifier(hidden_layer_sizes=(32,),batch_size=256,max_iter=120,
 early_stopping=True,validation_fraction=.12,n_iter_no_change=12,
 alpha=.3,learning_rate_init=.001,random_state=109)
model.fit(scale.transform(X),y)
pred=model.predict_proba(scale.transform(np.array(hold)))[:,1]
bgpred=model.predict_proba(scale.transform(negative_test))[:,1]
report=dict(synthetic_train_positive_windows=len(pos),negative_train_windows=len(neg),
 synthetic_holdout_positive_recall=float((pred[np.array(hold_y)==1]>=.5).mean()),
 synthetic_holdout_negative_false_rate=float((pred[np.array(hold_y)==0]>=.5).mean()),
 background_holdout_windows=len(bgpred),background_false_windows=int((bgpred>=.5).sum()),
 background_peak=float(bgpred.max()),iterations=model.n_iter_)
print(json.dumps(report),flush=True)
(ROOT/'training-report.json').write_text(json.dumps(report,indent=2))

# Fold standardization into the first layer. No pickle or host runtime is deployed.
w0=(model.coefs_[0]/scale.scale_[:,None]).T.astype('<f4')
b0=(model.intercepts_[0]-(scale.mean_/scale.scale_)@model.coefs_[0]).astype('<f4')
w1=model.coefs_[1].T.astype('<f4');b1=model.intercepts_[1].astype('<f4')
b=flatbuffers.Builder(300000)
def ints(values):
 b.StartVector(4,len(values),4)
 for v in reversed(values):b.PrependInt32(int(v))
 return b.EndVector()
def offsets(values):
 b.StartVector(4,len(values),4)
 for v in reversed(values):b.PrependUOffsetTRelative(v)
 return b.EndVector()
buffers=[]
for raw in [b'',w0.tobytes(),b0.tobytes(),w1.tobytes(),b1.tobytes()]:
 data=b.CreateByteVector(raw)
 tflite.BufferStart(b);tflite.BufferAddData(b,data);buffers.append(tflite.BufferEnd(b))
tensors=[]
for name,shape,buf in [('input',[1,16,96],0),('w0',[32,1536],1),('b0',[32],2),
 ('hidden',[1,32],0),('w1',[1,32],3),('b1',[1],4),('logit',[1,1],0),('score',[1,1],0)]:
 text=b.CreateString(name);dims=ints(shape)
 tflite.TensorStart(b);tflite.TensorAddName(b,text);tflite.TensorAddShape(b,dims)
 tflite.TensorAddType(b,tflite.TensorType.FLOAT32);tflite.TensorAddBuffer(b,buf)
 tensors.append(tflite.TensorEnd(b))
codes=[]
for code in [tflite.BuiltinOperator.FULLY_CONNECTED,tflite.BuiltinOperator.LOGISTIC]:
 tflite.OperatorCodeStart(b);tflite.OperatorCodeAddBuiltinCode(b,code)
 tflite.OperatorCodeAddDeprecatedBuiltinCode(b,code);tflite.OperatorCodeAddVersion(b,1)
 codes.append(tflite.OperatorCodeEnd(b))
ops=[]
for inputs,output,relu in [([0,1,2],3,True),([3,4,5],6,False)]:
 tflite.FullyConnectedOptionsStart(b)
 tflite.FullyConnectedOptionsAddFusedActivationFunction(b,tflite.ActivationFunctionType.RELU if relu else tflite.ActivationFunctionType.NONE)
 opt=tflite.FullyConnectedOptionsEnd(b);iv=ints(inputs);ov=ints([output])
 tflite.OperatorStart(b);tflite.OperatorAddOpcodeIndex(b,0);tflite.OperatorAddInputs(b,iv);tflite.OperatorAddOutputs(b,ov)
 tflite.OperatorAddBuiltinOptionsType(b,tflite.BuiltinOptions.FullyConnectedOptions);tflite.OperatorAddBuiltinOptions(b,opt)
 ops.append(tflite.OperatorEnd(b))
iv=ints([6]);ov=ints([7]);tflite.OperatorStart(b);tflite.OperatorAddOpcodeIndex(b,1)
tflite.OperatorAddInputs(b,iv);tflite.OperatorAddOutputs(b,ov);ops.append(tflite.OperatorEnd(b))
tv=offsets(tensors);iv=ints([0]);ov=ints([7]);opv=offsets(ops)
tflite.SubGraphStart(b);tflite.SubGraphAddTensors(b,tv);tflite.SubGraphAddInputs(b,iv)
tflite.SubGraphAddOutputs(b,ov);tflite.SubGraphAddOperators(b,opv);graph=tflite.SubGraphEnd(b)
gv=offsets([graph]);bv=offsets(buffers);cv=offsets(codes)
description=b.CreateString('Mira Arabic experimental, synthetic-only training; owner audio held out')
tflite.ModelStart(b);tflite.ModelAddVersion(b,3);tflite.ModelAddSubgraphs(b,gv)
tflite.ModelAddBuffers(b,bv);tflite.ModelAddOperatorCodes(b,cv);tflite.ModelAddDescription(b,description)
model_offset=tflite.ModelEnd(b);b.Finish(model_offset,file_identifier=b'TFL3')
(ROOT/'mira_ar_experimental.tflite').write_bytes(b.Output())
print('exported',len(b.Output()),flush=True)
