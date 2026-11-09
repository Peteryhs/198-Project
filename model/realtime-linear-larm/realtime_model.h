/* Generated float32 affine coefficients; inputs are 31 offline repetition features. */
#ifndef REALTIME_MODEL_H
#define REALTIME_MODEL_H
#include <math.h>
static const int RT_N_FEATURES=31, RT_N_EXERCISES=3;
static const float rt_exercise_coef[93]={0.195896009f, -2.97167697f, -4.58965505f, 3.99438168f, 5.42181186f, -5.64342446f, -5.70257214f, -0.402067457f, 0.33444264f, -0.229656901f, -0.0153188986f, 0.977423921f, -0.363422916f, 0.254980074f, 0.186284921f, -0.157613125f, 6.03185379f, 2.61118379f, -0.343471546f, 0.0355061019f, -0.11419845f, -0.0937965601f, -0.00845676551f, 3.65844008e-05f, 0.00850177885f, 2.43459772f, 2.9119799f, 0.99590449f, -5.86528671f, 4.49669011f, -4.53589217f, -0.24023942f, -0.858911014f, 1.70701436f, -3.05803014f, -0.700651051f, 5.43609635f, 0.209353772f, 0.214400089f, -0.156521796f, -0.224472404f, 2.0400063f, -0.677022919f, -0.751782583f, 0.461919684f, -0.176007193f, -0.551385267f, -4.91116599f, -0.563923f, 0.0719759196f, -0.159034328f, -0.188767545f, 0.0779134827f, -0.00496298052f, -0.022246578f, 0.0189234429f, 3.04511084f, -3.4735718f, -1.97839435f, 4.39068368f, -1.43744993f, 2.82155029f, 0.0443434103f, 3.83058798f, 2.88264069f, -0.936351548f, -4.72116081f, 0.207328112f, 5.49321836f, 0.187667368f, -0.177920844f, 0.454129305f, -2.0246874f, -0.300401002f, 1.1152055f, -0.716899758f, -0.0102777277f, 0.708998392f, -1.1206878f, -2.04726079f, 0.271495627f, 0.123528226f, 0.302965995f, 0.0158830774f, 0.013419746f, 0.0222099936f, -0.0274252217f, -5.47970856f, 0.561591898f, 0.982489856f, 1.47460303f, -3.05924018f, 1.71434188f};
static const float rt_exercise_intercept[3]={-5.98965039f, 2.130609f, 3.85904139f};
static const float rt_quality_coef[31]={-0.0423062446f, 0.818945521f, -0.645379065f, 2.07252555f, -6.2370364f, 6.16469224f, -6.87921191f, 1.22282876f, 0.173368651f, -1.55245436f, 4.05852855f, 0.181514106f, -0.0883550396f, 0.405067409f, -0.034964794f, 1.30760054f, 5.19112971f, -1.1255005f, 3.88164112f, -0.125382394f, -0.0595447953f, 0.158243162f, -0.00844456295f, 0.0094448931f, 0.0151511551f, -5.47871921f, 4.35678229f, -0.960449659f, -10.6209274f, -1.16159138f, -8.43770979f};
static const float rt_quality_intercept=-4.98017333f;
static inline float rt_sigmoid(float x){return 1.0f/(1.0f+expf(-x));}
static inline const char *rt_error_category(void){return "not enough evidence to say";}
static inline int rt_predict_rep(const float x[31], float ex[RT_N_EXERCISES], float *quality){
 for(int k=0;k<31;k++)if(!isfinite(x[k]))return 0;
 float z[RT_N_EXERCISES], mx=-INFINITY, sum=0.0f;
 for(int j=0;j<RT_N_EXERCISES;j++){z[j]=rt_exercise_intercept[j]; for(int k=0;k<31;k++)z[j]+=rt_exercise_coef[j*31+k]*x[k]; if(!isfinite(z[j]))return 0; if(z[j]>mx)mx=z[j];}
 for(int j=0;j<RT_N_EXERCISES;j++){ex[j]=expf(z[j]-mx);sum+=ex[j];} for(int j=0;j<RT_N_EXERCISES;j++)ex[j]/=sum;
 float q=rt_quality_intercept; for(int k=0;k<31;k++)q+=rt_quality_coef[k]*x[k]; if(!isfinite(q))return 0; *quality=rt_sigmoid(q);return 1;}
#endif
