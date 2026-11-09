/* Generated float32 affine coefficients; inputs are 31 repetition features. */
#ifndef REALTIME_MODEL_H
#define REALTIME_MODEL_H
#include <math.h>
static const int RT_N_FEATURES=31, RT_N_EXERCISES=3;
static const float rt_exercise_coef[93]={-0.253888093f, -0.390232228f, 7.74559605f, 2.11921321f, -0.0705726714f, -1.12186409f, 1.08025396f, -0.263971503f, -0.0712576168f, -0.303613255f, 0.126632657f, -0.760839368f, -0.421897871f, 0.166663553f, -0.288798406f, -0.142710281f, 6.63843428f, -0.125471367f, 2.63303325f, -0.00638340185f, 0.111117692f, 0.0516286559f, -0.0184504313f, 0.0442471807f, -0.00937464033f, -1.9980959f, 7.07964472f, -0.556426799f, 0.100318699f, -2.27899682f, 2.87436435f, 0.307365067f, 1.39947285f, -6.60603272f, -5.96661773f, 6.58405588f, 4.63834942f, -1.09596665f, -0.223844191f, 0.975555812f, 1.35701939f, -0.211177334f, 0.675152794f, 0.560023272f, -0.0451071084f, -0.210025165f, -0.39068494f, -1.03313613f, -2.65760008f, -1.08372122f, 0.0896430796f, -0.0864386535f, -0.174007533f, 0.00386959196f, 0.0239380325f, 0.0299954082f, 1.80700179f, -3.24012356f, 0.0558918089f, -1.14063892f, -1.84779987f, -6.67580096f, -0.0534769741f, -1.00924063f, -1.13956332f, 3.84740452f, -6.5134832f, -3.51648533f, 0.015712686f, 0.487815693f, -0.904298195f, -1.05340613f, 0.084544677f, 0.0856865749f, -0.1381254f, -0.121556444f, 0.49882357f, 0.533395221f, -5.60529815f, 2.78307145f, -1.54931203f, -0.0832596777f, -0.0246790383f, 0.122378877f, 0.0145808393f, -0.0681852132f, -0.0206207679f, 0.191094101f, -3.83952115f, 0.50053499f, 1.04032022f, 4.12679669f, 3.80143661f};
static const float rt_exercise_intercept[3]={-2.27127081f, -1.19754864f, 3.46881945f};
static const float rt_quality_coef[31]={-0.385569651f, -2.7042907f, -0.884072881f, 1.92186093f, -7.78620468f, 3.6928935f, 2.72667176f, 1.80820921f, -0.0148273748f, -0.277576238f, 2.83948765f, 0.627864474f, -0.495467673f, 1.02781848f, 0.27595531f, -0.215622836f, 5.67559343f, 0.795970556f, -0.0916102837f, -0.167748587f, -0.350363482f, -0.0090780645f, -0.0506686532f, 0.0109170839f, 0.143834298f, -5.38357334f, 0.821214193f, -1.88523211f, -9.72820149f, -1.87770477f, 4.99243355f};
static const float rt_quality_intercept=-2.13357845f;
static inline float rt_sigmoid(float x){return 1.0f/(1.0f+expf(-x));}
static inline const char *rt_error_category(void){return "not enough evidence to say";}
static inline int rt_predict_rep(const float x[31], float ex[RT_N_EXERCISES], float *quality){
 for(int k=0;k<RT_N_FEATURES;k++)if(!isfinite(x[k]))return 0;
 float z[RT_N_EXERCISES], mx=-INFINITY, sum=0.0f;
 for(int j=0;j<RT_N_EXERCISES;j++){z[j]=rt_exercise_intercept[j]; for(int k=0;k<RT_N_FEATURES;k++)z[j]+=rt_exercise_coef[j*RT_N_FEATURES+k]*x[k]; if(!isfinite(z[j]))return 0; if(z[j]>mx)mx=z[j];}
 for(int j=0;j<RT_N_EXERCISES;j++){ex[j]=expf(z[j]-mx);sum+=ex[j];} for(int j=0;j<RT_N_EXERCISES;j++)ex[j]/=sum;
 float q=rt_quality_intercept; for(int k=0;k<RT_N_FEATURES;k++)q+=rt_quality_coef[k]*x[k]; if(!isfinite(q))return 0; *quality=rt_sigmoid(q);return 1;}
#endif
