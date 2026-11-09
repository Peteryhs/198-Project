/* Generated float32 affine coefficients; inputs are 31 offline repetition features. */
#ifndef REALTIME_MODEL_H
#define REALTIME_MODEL_H
#include <math.h>
static const int RT_N_FEATURES=31, RT_N_EXERCISES=3;
static const float rt_exercise_coef[93]={0.136102613f, -2.32578196f, 0.0785071045f, 2.61405435f, 2.29955349f, 3.85835261f, -0.595176443f, -0.114118195f, 0.0975090736f, -0.348252957f, 0.239888228f, -0.229140468f, -0.268419461f, 0.150508103f, -0.197228527f, 0.00499609501f, 6.10736157f, -2.66671196f, 2.60622382f, 0.00653585937f, 0.0640537095f, -0.0405860342f, -0.00114224375f, 0.0263215446f, 0.00451370957f, -0.224132654f, 2.44859671f, -0.529480137f, -1.03872438f, 4.95399167f, -2.7526235f, -0.175675441f, 0.278979643f, -0.0625318548f, -5.1412709f, 4.92681557f, 1.98669409f, -3.55726116f, 0.464780077f, 0.257242015f, 0.375340798f, 0.327167202f, 0.03582663f, 0.20586356f, -0.0996902654f, -0.133977078f, -0.0555302001f, -4.85060307f, -0.31044729f, -0.528752877f, 0.0354828663f, -0.0450340502f, -0.1606085f, -0.00725463916f, 0.00432442546f, 0.0157164419f, 4.64797493f, -0.431594339f, -0.502327021f, 3.22539696f, -4.23818044f, 0.31301222f, 0.0395728277f, 2.04680231f, -0.0159752497f, 2.52721655f, -7.22636907f, -5.8450467f, 4.15243761f, -0.350661883f, -0.354751088f, -0.0270878415f, -0.56705543f, 0.193313838f, 0.062555901f, -0.0508178379f, 0.331205605f, 0.0505341051f, -1.2567585f, 2.97715925f, -2.07747095f, -0.0420187257f, -0.0190196593f, 0.201194534f, 0.00839688291f, -0.03064597f, -0.0202301515f, -4.42384228f, -2.01700237f, 1.03180716f, -2.18667259f, -0.715811237f, 2.43961128f};
static const float rt_exercise_intercept[3]={-5.68374054f, 1.77652149f, 3.90721906f};
static const float rt_quality_coef[31]={-0.0226852113f, -0.924009003f, -0.62317461f, 1.94243638f, -8.17265367f, 4.7224552f, -1.51621803f, 0.882083606f, 0.00605133925f, -0.404865334f, 2.97987669f, 0.533944604f, -0.0915043155f, 0.739235543f, 0.31848432f, 0.13836255f, 6.66740714f, -1.90010205f, 3.81922603f, -0.0437925297f, -0.0658264228f, 0.0918966351f, -0.0142968907f, -0.0127295782f, 0.0143444347f, -7.25229144f, 1.43096503f, -5.83807226f, -12.0568266f, 1.46889652f, -3.03589239f};
static const float rt_quality_intercept=-1.85899627f;
static inline float rt_sigmoid(float x){return 1.0f/(1.0f+expf(-x));}
static inline const char *rt_error_category(void){return "not enough evidence to say";}
static inline int rt_predict_rep(const float x[31], float ex[RT_N_EXERCISES], float *quality){
 for(int k=0;k<31;k++)if(!isfinite(x[k]))return 0;
 float z[RT_N_EXERCISES], mx=-INFINITY, sum=0.0f;
 for(int j=0;j<RT_N_EXERCISES;j++){z[j]=rt_exercise_intercept[j]; for(int k=0;k<31;k++)z[j]+=rt_exercise_coef[j*31+k]*x[k]; if(!isfinite(z[j]))return 0; if(z[j]>mx)mx=z[j];}
 for(int j=0;j<RT_N_EXERCISES;j++){ex[j]=expf(z[j]-mx);sum+=ex[j];} for(int j=0;j<RT_N_EXERCISES;j++)ex[j]/=sum;
 float q=rt_quality_intercept; for(int k=0;k<31;k++)q+=rt_quality_coef[k]*x[k]; if(!isfinite(q))return 0; *quality=rt_sigmoid(q);return 1;}
#endif
