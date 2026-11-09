/* Generated float32 affine coefficients; inputs are 31 offline repetition features. */
#ifndef REALTIME_MODEL_H
#define REALTIME_MODEL_H
#include <math.h>
static const int RT_N_FEATURES=31, RT_N_EXERCISES=3;
static const float rt_exercise_coef[93]={0.191829652f, -2.81804705f, -4.64018635f, 4.36091956f, 5.45377332f, -5.72638353f, -5.78720507f, -0.432790662f, 0.370826616f, -0.640656173f, -0.0617170633f, 0.971572948f, -0.698065472f, 0.265061922f, 0.184857966f, -0.162850022f, 5.79868227f, 2.63547461f, 0.037282555f, 0.0489544133f, -0.117439368f, -0.0411151873f, -0.0105608428f, -0.00415355634f, 0.0215022915f, 2.468835f, 2.76773771f, 0.925742578f, -6.05550388f, 4.48620607f, -4.73697074f, -0.236974166f, -0.998806481f, 1.77836687f, -3.63331739f, -0.760264395f, 5.46472138f, 0.251538384f, 0.224926964f, -0.224778243f, 0.225388379f, 2.08214084f, -0.697721605f, -0.358104568f, 0.451284813f, -0.159120451f, -0.584633019f, -4.56294335f, -0.569496202f, -0.196043582f, -0.164824371f, -0.180290905f, 0.0317344619f, -0.00301146702f, -0.0206680814f, 0.0090259344f, 2.92062061f, -3.32095363f, -1.94118706f, 4.49617174f, -1.40022694f, 2.98641996f, 0.0451445142f, 3.81685353f, 2.86181948f, -0.727602168f, -4.69350892f, 0.261662153f, 5.53566669f, 0.207863698f, -0.146048373f, 0.415267794f, -2.02042378f, -0.273851343f, 1.05617004f, -0.716346735f, -0.0257375151f, 0.747483041f, -1.23573892f, -2.06597841f, 0.158761028f, 0.115869957f, 0.297730273f, 0.00938072541f, 0.0135723098f, 0.0248216377f, -0.0305282259f, -5.38945562f, 0.553215919f, 1.01544448f, 1.55933215f, -3.08597913f, 1.75055078f};
static const float rt_exercise_intercept[3]={-5.81294105f, 1.95415235f, 3.8587887f};
static const float rt_quality_coef[31]={-0.0446799462f, 0.85127225f, -0.655886782f, 2.12484003f, -6.24237019f, 6.24031191f, -6.93044601f, 1.19587273f, 0.184169191f, -1.60696822f, 4.08421632f, 0.172679642f, -0.151162983f, 0.392097703f, -0.0422346687f, 1.29264853f, 5.18133574f, -1.11877632f, 4.03783505f, -0.124840875f, -0.0559635273f, 0.162684482f, -0.00935056468f, 0.0117930476f, 0.015723113f, -5.51310857f, 4.32637259f, -1.06086906f, -10.555341f, -1.18703242f, -8.50398696f};
static const float rt_quality_intercept=-4.96893181f;
static inline float rt_sigmoid(float x){return 1.0f/(1.0f+expf(-x));}
static inline const char *rt_error_category(void){return "not enough evidence to say";}
static inline int rt_predict_rep(const float x[31], float ex[RT_N_EXERCISES], float *quality){
 for(int k=0;k<31;k++)if(!isfinite(x[k]))return 0;
 float z[RT_N_EXERCISES], mx=-INFINITY, sum=0.0f;
 for(int j=0;j<RT_N_EXERCISES;j++){z[j]=rt_exercise_intercept[j]; for(int k=0;k<31;k++)z[j]+=rt_exercise_coef[j*31+k]*x[k]; if(!isfinite(z[j]))return 0; if(z[j]>mx)mx=z[j];}
 for(int j=0;j<RT_N_EXERCISES;j++){ex[j]=expf(z[j]-mx);sum+=ex[j];} for(int j=0;j<RT_N_EXERCISES;j++)ex[j]/=sum;
 float q=rt_quality_intercept; for(int k=0;k<31;k++)q+=rt_quality_coef[k]*x[k]; if(!isfinite(q))return 0; *quality=rt_sigmoid(q);return 1;}
#endif
