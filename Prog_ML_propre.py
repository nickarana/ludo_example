## Import des packages
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import lightgbm as lgbm
from scipy.stats import norm
from joblib import dump,load
from sklearn.model_selection import GridSearchCV

#### DICO DONNEES
# TacticType : 0 - Normal
# TacticType : 1 - Pressing
# TacticType : 2 - Contre-attaques
# TacticType : 3 - Attaque au centre
# TacticType : 4 - Attaque sur les ailes
# TacticType : 7 - Jeu créatif
# TacticType : 8 - Tirs lointains


# Récupération des données à partir des fichiers CSV de Nickarana
df=pd.DataFrame()
event_id=pd.read_csv('eventid.csv')
event_id=event_id[(event_id['EventTypeID'].isin([1,2,7])) & (event_id['EventResultID']==1)]
liste_event_goals=event_id['EventID'].unique()
for i in [74,75,77]:
    exec("event_"+str(i)+"=pd.read_csv('event_"+str(i)+".csv')")
    # Import du fichier des évènements
    exec("event_"+str(i)+"=pd.read_csv('event_"+str(i)+".csv',low_memory=False)")
    # On ne conserve que les buts marqués
    exec("event_"+str(i)+"=event_"+str(i)+"[event_"+str(i)+"['EventID'].isin(liste_event_goals)].drop(['SubjectPlayerID','ObjectPlayerID'],axis=1).sort_values(by=['MatchID','EventMinute','TeamID'])")
    # Si buts dans les arrêts de jeu, on plafonne à 90 minutes
    exec("event_"+str(i)+".loc[event_"+str(i)+"['EventMinute']>90,'EventMinute']=90")
    # Incrémentation du nombre de buts marqués
    exec("event_"+str(i)+"['Num_goal']=event_"+str(i)+".groupby(['MatchID','TeamID']).cumcount()+1")
    # Récupération du nombre de buts de l'adversaire au moment du but marqué
    exec("event_"+str(i)+".loc[event_"+str(i)+"['MatchID']!=event_"+str(i)+"['MatchID'].shift(1),'Num_goal_opp']=0")
    exec("event_"+str(i)+".loc[(event_"+str(i)+"['TeamID']!=event_"+str(i)+"['TeamID'].shift(1)) & (event_"+str(i)+"['MatchID']==event_"+str(i)+"['MatchID'].shift(1)),'Num_goal_opp']=event_"+str(i)+"['Num_goal'].shift(1)")
    for j in range(0,15):
        exec("event_"+str(i)+".loc[(event_"+str(i)+"['MatchID']==event_"+str(i)+"['MatchID'].shift(1)) & (event_"+str(i)+"['TeamID']==event_"+str(i)+"['TeamID'].shift(1)),'Num_goal_opp']=event_"+str(i)+"['Num_goal_opp'].shift(1)")
   # Calcul du temps que va durer l'écart
    exec("event_"+str(i)+".loc[event_"+str(i)+"['MatchID']==event_"+str(i)+"['MatchID'].shift(-1),'EventMinute']=event_"+str(i)+"['EventMinute'].shift(-1)-event_"+str(i)+"['EventMinute']")
    exec("event_"+str(i)+".loc[event_"+str(i)+"['MatchID']!=event_"+str(i)+"['MatchID'].shift(-1),'EventMinute']=90-event_"+str(i)+"['EventMinute']")
    # Calcul de la pénalité attaque et du bonus défense
    exec("event_"+str(i)+"['Pen_att']=.91**(event_"+str(i)+"['Num_goal']-event_"+str(i)+"['Num_goal_opp']-1)")
    exec("event_"+str(i)+".loc[event_"+str(i)+"['Num_goal']-event_"+str(i)+"['Num_goal_opp']<2,'Pen_att']=1")
    exec("event_"+str(i)+"['Bon_def']=1.075**(event_"+str(i)+"['Num_goal']-event_"+str(i)+"['Num_goal_opp']-1)")
    exec("event_"+str(i)+".loc[event_"+str(i)+"['Num_goal']-event_"+str(i)+"['Num_goal_opp']<2,'Bon_def']=1")
    exec("event_"+str(i)+"=event_"+str(i)+".assign(Pen_att=event_"+str(i)+"['EventMinute']*event_"+str(i)+"['Pen_att'],Bon_def=event_"+str(i)+"['EventMinute']*event_"+str(i)+"['Bon_def']).groupby(['MatchID','TeamID'],as_index=False).agg({'EventMinute':'sum','Pen_att':'sum','Bon_def':'sum','Num_goal':'max'})")
    exec("event_"+str(i)+"['Pen_att']=(event_"+str(i)+"['Pen_att']+(90-event_"+str(i)+"['EventMinute']))/90")
    exec("event_"+str(i)+"['Bon_def']=(event_"+str(i)+"['Bon_def']+(90-event_"+str(i)+"['EventMinute']))/90")
    
    # Import de la base des matchs
    exec("df_"+str(i)+"=pd.read_csv('matchteam_"+str(i)+".csv').drop_duplicates().drop(['Location', \
         'Formation','PossH1','PossH2'],axis=1)")
    # Suppression des matchs avec forfait
    exec("df_"+str(i)+"=df_"+str(i)+"[df_"+str(i)+"['RatingMidfield']>0]")
    # On écarte les matchs avec prolongation
    exec("match_"+str(i)+"=pd.read_csv('match_"+str(i)+".csv',low_memory=False).drop_duplicates()")
    exec("df_"+str(i)+"=df_"+str(i)+".merge(match_"+str(i)+"[match_"+str(i)+"['MatchLengthID']==1]['MatchID'],on='MatchID',how='inner').drop_duplicates()")
    exec("df_"+str(i)+"=df_"+str(i)+".merge(event_"+str(i)+"[['MatchID','TeamID','Pen_att','Bon_def','Num_goal']],on=['MatchID','TeamID'],how='left')")
    # Ajout des données à la saison précédemment récupérée
    exec("df=pd.concat([df,df_"+str(i)+"],axis=0)")
    #exec("del df_"+str(i)+",match_"+str(i)+",event_"+str(i))
    

# Estimation de la baisse de notes due au repli défensif, puis correction
# Lorsque les minutes des buts ne sont pas disponibles, on ne conserve pas l'observation 
# Lorsque 0 but, la pénalité est forcée à 1 
df['Num_goal']=df['Num_goal'].fillna(0)
df=df[(df['Goals']==df['Num_goal'])]
df['Pen_att']=df['Pen_att'].fillna(1)
df['Bon_def']=df['Bon_def'].fillna(1)
for i in ['RatingRightAtt','RatingLeftAtt','RatingMidAtt']:
    df[i]=df[i]/df['Pen_att']
for i in ['RatingRightDef','RatingLeftDef','RatingMidDef']:
    df[i]=df[i]/df['Bon_def']
    
df['TacticType']=df['TacticType'].astype(str)

### On récupère les notes de l'adversaire
df1=df.drop(['TeamID','Goals','Pen_att','Bon_def','Num_goal'],
    axis=1).rename({'RatingMidfield':'RatingMidfield_adv',
    'RatingRightDef':'RatingRightDef_adv','RatingMidDef':'RatingMidDef_adv',
    'RatingLeftDef':'RatingLeftDef_adv','RatingRightAtt':'RatingRightAtt_adv',
    'RatingMidAtt':'RatingMidAtt_adv','RatingLeftAtt':'RatingLeftAtt_adv',
    'RatingISPDef':'RatingISPDef_adv','RatingISPAtt':'RatingISPAtt_adv',
    'TacticSkill':'TacticSkill_adv','TacticType':'TacticType_adv','Opp_TeamID':'TeamID'},axis=1)
                    
# Ajout des notes adverses                    
df=df.merge(df1,on=['MatchID','TeamID'],how='left')
del df1

# Nettoyage de la table df
df=df.drop(['Opp_TeamID','Pen_att','Bon_def','Num_goal'],axis=1)

# On supprime les matchs pour lesquels on dispose que d'une seule ligne
df_nb=df.groupby('MatchID').agg({'TeamID':'count'})
df=df[~df['MatchID'].isin(df_nb[df_nb['TeamID']==1].index.unique())]
del df_nb

# Création d'un ID unique
df['ID']=df['MatchID'].astype(str)+'_'+df['TeamID'].astype(str)

# Calcul des ratios
df['MidfieldRatio']=df['RatingMidfield']**3/(df['RatingMidfield']**3+df['RatingMidfield_adv']**3)
df['RightAttRatio']=.92*df['RatingRightAtt']**3.5/(df['RatingRightAtt']**3.5+df['RatingLeftDef_adv']**3.5)
df['LeftAttRatio']=.92*df['RatingLeftAtt']**3.5/(df['RatingLeftAtt']**3.5+df['RatingRightDef_adv']**3.5)
df['MidAttRatio']=.92*df['RatingMidAtt']**3.5/(df['RatingMidAtt']**3.5+df['RatingMidDef_adv']**3.5)
df['RightAtt_advRatio']=.92*df['RatingRightAtt_adv']**3.5/(df['RatingRightAtt_adv']**3.5+df['RatingLeftDef']**3.5)
df['LeftAtt_advRatio']=.92*df['RatingLeftAtt_adv']**3.5/(df['RatingLeftAtt_adv']**3.5+df['RatingRightDef']**3.5)
df['MidAtt_advRatio']=.92*df['RatingMidAtt_adv']**3.5/(df['RatingMidAtt_adv']**3.5+df['RatingMidDef']**3.5)
df['ISPAttRatio']=.92*df['RatingISPAtt']**3.5/(df['RatingISPAtt']**3.5+df['RatingISPDef_adv']**3.5)
df['ISPAtt_advRatio']=.92*df['RatingISPAtt_adv']**3.5/(df['RatingISPAtt_adv']**3.5+df['RatingISPDef']**3.5)

# Analyse des notes, pour voir s'il n'y a pas des matchs à virer...
df=df.drop(['RatingMidfield','RatingMidfield_adv','RatingRightAtt',
                'RatingRightAtt_adv','RatingMidAtt','RatingMidAtt_adv','RatingLeftAtt',
                'RatingLeftAtt_adv','RatingRightDef','RatingRightDef_adv',
                'RatingLeftDef','RatingLeftDef_adv','RatingMidDef','RatingMidDef_adv',
                'RatingISPAtt','RatingISPDef','RatingISPAtt_adv','RatingISPDef_adv'],axis=1)

# Split entre base de test et base de training
train, test=train_test_split(df,test_size=.2)
del df
train['train']=1
test['train']=0

#test2=test.copy()
# Les tables test et train sont concaténées afin que le target encoding puisse aussi se faire sur 
df = train.append(test)
del train
df.loc[df['train']==0,'Goals']=np.nan

# Traitement des variables catégorielles
# One-hot encoding
df=pd.concat([df,pd.get_dummies(df['TacticType'],prefix='TacticType'),pd.get_dummies(df['TacticType_adv'],prefix='TacticType_adv')],axis=1)
df=df.drop(['TacticType','TacticType_adv','TacticType_0','TacticType_adv_0'],axis=1)

df['TacticSkill_1']=df['TacticSkill']*df['TacticType_1']
df['TacticSkill_2']=df['TacticSkill']*df['TacticType_2']
df['TacticSkill_3']=df['TacticSkill']*df['TacticType_3']
df['TacticSkill_4']=df['TacticSkill']*df['TacticType_4']
df['TacticSkill_7']=df['TacticSkill']*df['TacticType_7']
df['TacticSkill_8']=df['TacticSkill']*df['TacticType_8']
df['TacticSkill_adv_1']=df['TacticSkill_adv']*df['TacticType_adv_1']
df['TacticSkill_adv_2']=df['TacticSkill_adv']*df['TacticType_adv_2']
df['TacticSkill_adv_3']=df['TacticSkill_adv']*df['TacticType_adv_3']
df['TacticSkill_adv_4']=df['TacticSkill_adv']*df['TacticType_adv_4']
df['TacticSkill_adv_7']=df['TacticSkill_adv']*df['TacticType_adv_7']
df['TacticSkill_adv_8']=df['TacticSkill_adv']*df['TacticType_adv_8']

df2=df.drop(['TacticType_adv_2',
             'TacticType_adv_4','TacticType_adv_3',
             'TacticType_adv_8','TacticSkill','TacticSkill_adv',
             'TacticType_adv_1','TacticType_adv_7','TacticType_1',
             'TacticType_2','TacticType_3','TacticType_4','TacticType_7',
             'TacticType_8','TacticSkill_adv_8','TacticSkill_adv_3','TacticSkill_adv_4',
             'TacticSkill_adv_2','ISPAtt_advRatio'],axis=1)

# On ne conserve que les variables numériques, car seules elles pourront entrer dans le LGBM
dtypes = df2.drop(['MatchID','TeamID'],axis=1).dtypes.map(str)
numerical_features = list(dtypes[dtypes.isin(['int64','float64','float32','int32','uint8'])].index)
X_full = df2.drop(['MatchID','TeamID'],axis=1)[numerical_features].copy()


# Préparation de la base de modélisation
X = X_full[(X_full['train'] == 1)].copy()
X_test = X_full[X_full['train'] == 0].copy()
y = X_full[(X_full['train'] == 1)]['Goals']
del X_full
indexes=pd.DataFrame(df2[df2['train']==0]['ID'],columns={'ID'}).drop_duplicates()
val_reelles=indexes.merge(test[['ID','Goals']].drop_duplicates(),on='ID',how='left')
del df2, indexes
y_test=val_reelles['Goals']

X.drop(['Goals', 'train'], axis=1, inplace=True)
X_test.drop(['Goals', 'train'], axis=1, inplace=True)

# Tuning des hyperparamètres
params = {
    'num_leaves': [150], # Affiner après le n_estimators
    'n_estimators': [1363],# A LANCER
    'max_depth':[8],
    #'boosting_type':['gbdt'],
    #'subsample_for_bin':[100000],
    'learning_rate':[.05]
    #'reg_alpha':[.01,.1]
    #'reg_lambda':[.01,.1]
}

grid = GridSearchCV(lgbm.LGBMRegressor(random_state=0), params, scoring='neg_root_mean_squared_error', cv=5, verbose=4)
grid.fit(X,y)
print(grid.best_estimator_)
print(grid.best_score_)
grid.cv_results_

# Algorithme Light GBM
model=lgbm.LGBMRegressor(num_leaves=150,
                              n_estimators=10000,early_stopping_round=10,max_depth=8,
                              #boosting_type='gbdt',subsample_for_bin=150000,
                              learning_rate=.05,#reg_lambda=.01#,
                              #min_child_samples=30,
                              random_state=0) # RMSE : 1.08847 (NL=150,MD=8,LR=.05)
model.fit(X, y,eval_set=[(X_test,y_test)],eval_metric='l2_root')
model.score(X,y)
model.score(X_test,y_test)
# Prédictions sur l'échantillon test
y_pred=model.predict(X_test,num_iteration=model.best_iteration_)
# Calcul du R² sur la base de test
accuracy = round(model.score(X_test,y_test)*100,2)
print(accuracy)

# Feature importances
pd.concat([pd.DataFrame(model.feature_importances_),pd.DataFrame(model.feature_name_)],axis=1)


### SAUVEGARDE DU MODELE
#dump(model,'lgbm.joblib')
#model=load('lgbm.joblib')