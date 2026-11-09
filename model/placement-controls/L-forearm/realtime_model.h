/* Generated float32 affine coefficients; inputs are 31 repetition features. */
#ifndef REALTIME_MODEL_H
#define REALTIME_MODEL_H
#include <math.h>
static const int RT_N_FEATURES=31, RT_N_EXERCISES=3;
static const float rt_exercise_coef[93]={-0.0937409662f, -0.884147022f, -6.20038948f, 1.49874023f, 1.78754346f, -0.362126723f, 3.05037231f, 0.191744252f, 0.904163517f, 0.220015061f, 0.127905076f, 0.24799985f, -0.102293464f, 0.000193357094f, -0.235693828f, -0.208318696f, 3.18196746f, 0.593808264f, 3.87253504f, -0.0334228909f, -0.257118794f, 0.0870126554f, 0.00754595952f, 0.0389229759f, -0.0227795658f, 1.15045723f, 4.79681099f, -2.82897716f, -1.15710846f, 1.44227951f, 0.397592049f, 0.135899367f, 0.184938207f, 6.62303029f, -5.32652985f, 5.87708997f, 5.12427679f, -2.41426263f, -0.467942219f, -0.466980525f, 0.819867609f, -0.170806347f, -0.858406302f, 0.267618878f, 0.0777731857f, -0.308147898f, -0.267282639f, 0.129085128f, -5.43559333f, -3.72908993f, 0.0549508122f, 0.0619285686f, -0.190168642f, 0.0157747247f, -0.0072859078f, 0.0644081425f, 1.57709461f, -0.608191007f, 3.06970434f, 1.77320953f, -5.54363529f, -3.91608847f, -0.0421584008f, 0.699208814f, -0.422640806f, 3.82778962f, -7.66463342f, -4.76215006f, -0.636109678f, 0.276197967f, -0.437182992f, -1.03988267f, 0.0429012704f, 0.610406452f, -0.165325413f, -0.0779665428f, 0.543841726f, 0.475601336f, -3.31105258f, 4.84178507f, -0.143445112f, -0.0215279214f, 0.195190226f, 0.103155986f, -0.0233206842f, -0.0316370681f, -0.0416285767f, -2.72755184f, -4.18861998f, -0.240727181f, -0.616101073f, 4.10135578f, 3.51849642f};
static const float rt_exercise_intercept[3]={-3.08873333f, 0.280195852f, 2.80853748f};
static const float rt_quality_coef[31]={-0.365333128f, -3.48951109f, 1.34331172f, 4.20663372f, -8.01035417f, 4.51086695f, -1.58783111f, 2.26581381f, -0.683749973f, -1.17705308f, 3.19845988f, -0.153486428f, -0.300700003f, 0.936204352f, 0.198283438f, 0.449240914f, 7.33970568f, -6.66125917f, 1.55782394f, -0.163402282f, 0.407247985f, 0.15585001f, -0.0309240454f, -0.0121029789f, 0.0428470321f, -6.23519788f, 7.50371445f, -4.06256416f, -9.75141396f, 0.551024758f, 3.13820245f};
static const float rt_quality_intercept=-1.74040109f;
static inline float rt_sigmoid(float x){return 1.0f/(1.0f+expf(-x));}
static inline const char *rt_error_category(void){return "not enough evidence to say";}
static inline int rt_predict_rep(const float x[31], float ex[RT_N_EXERCISES], float *quality){
 for(int k=0;k<RT_N_FEATURES;k++)if(!isfinite(x[k]))return 0;
 float z[RT_N_EXERCISES], mx=-INFINITY, sum=0.0f;
 for(int j=0;j<RT_N_EXERCISES;j++){z[j]=rt_exercise_intercept[j]; for(int k=0;k<RT_N_FEATURES;k++)z[j]+=rt_exercise_coef[j*RT_N_FEATURES+k]*x[k]; if(!isfinite(z[j]))return 0; if(z[j]>mx)mx=z[j];}
 for(int j=0;j<RT_N_EXERCISES;j++){ex[j]=expf(z[j]-mx);sum+=ex[j];} for(int j=0;j<RT_N_EXERCISES;j++)ex[j]/=sum;
 float q=rt_quality_intercept; for(int k=0;k<RT_N_FEATURES;k++)q+=rt_quality_coef[k]*x[k]; if(!isfinite(q))return 0; *quality=rt_sigmoid(q);return 1;}
#endif
