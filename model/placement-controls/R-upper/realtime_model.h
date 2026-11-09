/* Generated float32 affine coefficients; inputs are 31 repetition features. */
#ifndef REALTIME_MODEL_H
#define REALTIME_MODEL_H
#include <math.h>
static const int RT_N_FEATURES=31, RT_N_EXERCISES=3;
static const float rt_exercise_coef[93]={-0.21138286f, -1.4642295f, 2.24302764f, -0.215240705f, 1.22795952f, -4.87116371f, 1.33305992f, -1.77293182f, -0.0115141192f, 0.673723371f, -0.832919161f, -0.0200183313f, -0.333917009f, 1.03786287f, -0.0107394478f, -1.0441982f, 1.90483336f, -0.013371125f, 6.25968502f, 0.156643665f, -0.0572536052f, -0.0813259914f, 0.0364084381f, 0.0897031728f, 0.0674965623f, 4.31075908f, 4.41475896f, -3.45702357f, -2.66052225f, 2.02675359f, -5.77164053f, 0.365609251f, -0.496874084f, -0.94278496f, -2.71946887f, 5.1910221f, 5.53727572f, -0.645446109f, 0.948074513f, 0.656797817f, 0.891738628f, 1.06734741f, 0.120427085f, 1.09953614f, -0.362625219f, -0.258117045f, 0.405640517f, -3.33885185f, 2.59757596f, -6.05749216f, -0.213974443f, 0.339019007f, -0.277068134f, -0.112783401f, -0.00738028349f, 0.0177706062f, 0.777855187f, -9.58272729f, -0.314900702f, 6.4135693f, -3.40592943f, 2.69362115f, -0.15422639f, 1.96110358f, -1.30024268f, 2.93470957f, -6.41898162f, -0.666112006f, -0.687613813f, 0.824857307f, -0.645283698f, -1.565462f, -0.234428247f, -0.100408754f, -0.765619131f, -0.675237648f, 0.268856492f, 0.638557682f, 1.43401849f, -2.58420483f, -0.202192861f, 0.0573307781f, -0.281765402f, 0.358394126f, 0.0763749632f, -0.0823228893f, -0.0852671685f, -5.08861427f, 5.16796832f, 3.77192427f, -3.75304705f, 1.37917585f, 3.07801938f};
static const float rt_exercise_intercept[3]={-2.62396118f, 1.80870387f, 0.815257313f};
static const float rt_quality_coef[31]={-0.149864902f, -0.4213325f, -1.01652061f, -0.102532216f, -8.22563334f, 13.4573718f, -8.40808544f, 0.776740116f, 0.678283243f, -0.892468845f, 4.1891794f, 0.473830716f, -0.107776783f, 0.728171504f, 0.0314001086f, 0.745246182f, 11.8360439f, -0.568177243f, 4.95063932f, 0.0950671259f, -0.310293203f, 0.175450996f, 0.0413318469f, 0.0402513149f, -0.0211085079f, -13.1917053f, -0.983331741f, -4.07476033f, -9.04769217f, -2.05656339f, -2.5775186f};
static const float rt_quality_intercept=-3.39755904f;
static inline float rt_sigmoid(float x){return 1.0f/(1.0f+expf(-x));}
static inline const char *rt_error_category(void){return "not enough evidence to say";}
static inline int rt_predict_rep(const float x[31], float ex[RT_N_EXERCISES], float *quality){
 for(int k=0;k<RT_N_FEATURES;k++)if(!isfinite(x[k]))return 0;
 float z[RT_N_EXERCISES], mx=-INFINITY, sum=0.0f;
 for(int j=0;j<RT_N_EXERCISES;j++){z[j]=rt_exercise_intercept[j]; for(int k=0;k<RT_N_FEATURES;k++)z[j]+=rt_exercise_coef[j*RT_N_FEATURES+k]*x[k]; if(!isfinite(z[j]))return 0; if(z[j]>mx)mx=z[j];}
 for(int j=0;j<RT_N_EXERCISES;j++){ex[j]=expf(z[j]-mx);sum+=ex[j];} for(int j=0;j<RT_N_EXERCISES;j++)ex[j]/=sum;
 float q=rt_quality_intercept; for(int k=0;k<RT_N_FEATURES;k++)q+=rt_quality_coef[k]*x[k]; if(!isfinite(q))return 0; *quality=rt_sigmoid(q);return 1;}
#endif
