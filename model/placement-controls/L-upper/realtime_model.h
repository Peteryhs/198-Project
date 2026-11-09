/* Generated float32 affine coefficients; inputs are 31 repetition features. */
#ifndef REALTIME_MODEL_H
#define REALTIME_MODEL_H
#include <math.h>
static const int RT_N_FEATURES=31, RT_N_EXERCISES=3;
static const float rt_exercise_coef[93]={0.146567693f, -3.8736748f, -3.82941318f, 2.97694377f, 2.3714212f, -7.9755167f, 2.65857815f, -1.18447756f, -0.0458537736f, 0.725852972f, -0.974142156f, 0.517403321f, -0.0192814564f, 0.525432981f, 0.297452317f, -0.826425441f, 2.55941169f, 1.10739666f, 1.33725474f, 0.0767145363f, 0.0462886088f, 0.0173071813f, 0.00857230343f, 0.0345808262f, 0.00954962397f, 7.07454968f, 5.81899801f, -0.104940734f, -6.12013976f, 0.723879873f, -1.89541024f, -0.0830949065f, -0.95464966f, 2.32839804f, -8.0219198f, 2.8658314f, 8.09511147f, -2.31635252f, 0.678453974f, 0.0432264605f, 1.55765894f, 2.58951967f, -0.575844061f, 0.785391274f, 0.38446544f, -0.325358716f, -0.632139914f, -1.41754562f, 0.954846838f, 2.05037175f, -0.174850029f, -0.327445647f, -0.34076415f, -0.00675728077f, -0.0255766272f, 0.0399871602f, -1.69924016f, -9.74977794f, -5.38354364f, 6.06023021f, 1.02326245f, 2.01945306f, -0.0634727862f, 4.82832446f, 1.50101515f, 5.04497604f, -5.2372526f, -0.119594772f, -0.342225627f, 0.506023588f, 0.00262731313f, -2.28351191f, -1.61537752f, 0.0584407402f, -0.766109818f, -0.909898421f, 0.0279063989f, 1.45856535f, -1.14186606f, -2.0622435f, -3.38762648f, 0.0981354929f, 0.281157038f, 0.323456969f, -0.00181502266f, -0.00900419902f, -0.0495367842f, -5.37530952f, 3.93077993f, 5.48848437f, 0.0599095534f, -1.74714232f, -0.124042818f};
static const float rt_exercise_intercept[3]={-3.92738156f, 1.26387402f, 2.66350754f};
static const float rt_quality_coef[31]={-0.410970035f, -2.3837408f, 0.803225837f, 3.68824833f, -5.75557323f, 8.19360399f, -14.1494373f, 2.27340716f, -0.200607631f, -2.16191031f, 4.26104666f, -0.395864784f, 0.630908553f, -0.201664262f, -0.0557360236f, 3.25315118f, 8.84493755f, -2.31707077f, 1.46104047f, -0.164915213f, 0.269156318f, 0.130866817f, -0.00789534663f, 0.0478247749f, -0.0242957698f, -7.64004788f, 4.21043193f, -0.842189332f, -10.402011f, -3.1779529f, -7.2918082f};
static const float rt_quality_intercept=-3.83430546f;
static inline float rt_sigmoid(float x){return 1.0f/(1.0f+expf(-x));}
static inline const char *rt_error_category(void){return "not enough evidence to say";}
static inline int rt_predict_rep(const float x[31], float ex[RT_N_EXERCISES], float *quality){
 for(int k=0;k<RT_N_FEATURES;k++)if(!isfinite(x[k]))return 0;
 float z[RT_N_EXERCISES], mx=-INFINITY, sum=0.0f;
 for(int j=0;j<RT_N_EXERCISES;j++){z[j]=rt_exercise_intercept[j]; for(int k=0;k<RT_N_FEATURES;k++)z[j]+=rt_exercise_coef[j*RT_N_FEATURES+k]*x[k]; if(!isfinite(z[j]))return 0; if(z[j]>mx)mx=z[j];}
 for(int j=0;j<RT_N_EXERCISES;j++){ex[j]=expf(z[j]-mx);sum+=ex[j];} for(int j=0;j<RT_N_EXERCISES;j++)ex[j]/=sum;
 float q=rt_quality_intercept; for(int k=0;k<RT_N_FEATURES;k++)q+=rt_quality_coef[k]*x[k]; if(!isfinite(q))return 0; *quality=rt_sigmoid(q);return 1;}
#endif
