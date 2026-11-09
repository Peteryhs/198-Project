/* Generated float32 affine coefficients; inputs are 31 offline repetition features. */
#ifndef REALTIME_MODEL_H
#define REALTIME_MODEL_H
#include <math.h>
static const int RT_N_FEATURES=31, RT_N_EXERCISES=3;
static const float rt_exercise_coef[93]={0.131994417f, -2.43004415f, 0.0133100602f, 2.48330301f, 1.99534118f, 4.29139151f, -1.0488391f, -0.13410281f, 0.171872258f, -0.365828805f, 0.353669533f, -0.247941229f, -0.209656723f, 0.202915933f, -0.279161562f, 0.0780460309f, 6.35801915f, -2.70561591f, 2.32906661f, -0.00405658802f, 0.0531157494f, -0.0569565618f, 0.00129944022f, 0.0299691388f, -0.00389199585f, -0.43402141f, 2.4290163f, -0.088626693f, -1.1302351f, 5.05082886f, -2.78225124f, -0.169614715f, 0.230511342f, -0.104492665f, -5.09087344f, 5.09193273f, 2.02134326f, -3.01915372f, 0.515885497f, 0.266170909f, 0.409320271f, 0.383739378f, 0.0662046426f, 0.117940315f, -0.115916421f, -0.12905146f, -0.157668182f, -5.33889012f, -0.234595104f, 0.0264936577f, 0.0349960933f, -0.0435334893f, -0.155020196f, -0.00762357379f, 0.00198166674f, 0.0248661321f, 4.85438847f, -0.593655998f, -1.44171528f, 3.33107687f, -4.21444148f, 0.297494819f, 0.0376202979f, 2.19953281f, 0.0911826052f, 2.60757043f, -7.08727391f, -6.31273477f, 4.06799282f, -0.381782688f, -0.438043166f, -0.0434914658f, -0.737408911f, 0.181736586f, 0.0917164085f, -0.0869995116f, 0.408213022f, 0.0796221516f, -1.01912903f, 2.94021102f, -2.35556027f, -0.0309395053f, -0.00958226004f, 0.211976758f, 0.00632413357f, -0.0319508055f, -0.0209741362f, -4.42036706f, -1.83536031f, 1.53034197f, -2.20084177f, -0.836387382f, 2.48475642f};
static const float rt_exercise_intercept[3]={-5.65239824f, 1.90184309f, 3.75055515f};
static const float rt_quality_coef[31]={-0.0267630865f, -0.942547456f, -0.231869741f, 1.9443486f, -8.07781711f, 3.89859363f, -1.31672741f, 0.876966102f, -0.268480345f, -0.343611045f, 2.97949423f, 0.420242842f, -0.139019612f, 0.689762227f, 0.45825671f, 0.108225628f, 6.77864239f, -1.95591559f, 3.80238068f, -0.0438637932f, -0.0230311308f, 0.0895044885f, -0.014209291f, -0.016085184f, 0.0154250064f, -7.21638037f, 1.60226681f, -5.70888781f, -12.053838f, 1.20486541f, -3.06049635f};
static const float rt_quality_intercept=-1.94872249f;
static inline float rt_sigmoid(float x){return 1.0f/(1.0f+expf(-x));}
static inline const char *rt_error_category(void){return "not enough evidence to say";}
static inline int rt_predict_rep(const float x[31], float ex[RT_N_EXERCISES], float *quality){
 for(int k=0;k<31;k++)if(!isfinite(x[k]))return 0;
 float z[RT_N_EXERCISES], mx=-INFINITY, sum=0.0f;
 for(int j=0;j<RT_N_EXERCISES;j++){z[j]=rt_exercise_intercept[j]; for(int k=0;k<31;k++)z[j]+=rt_exercise_coef[j*31+k]*x[k]; if(!isfinite(z[j]))return 0; if(z[j]>mx)mx=z[j];}
 for(int j=0;j<RT_N_EXERCISES;j++){ex[j]=expf(z[j]-mx);sum+=ex[j];} for(int j=0;j<RT_N_EXERCISES;j++)ex[j]/=sum;
 float q=rt_quality_intercept; for(int k=0;k<31;k++)q+=rt_quality_coef[k]*x[k]; if(!isfinite(q))return 0; *quality=rt_sigmoid(q);return 1;}
#endif
