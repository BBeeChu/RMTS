import os
import argparse
import torch as th
from utils import *
from models.customized_modeling_t5 import CustomizedT5ForConditionalGeneration
from transformers import T5Tokenizer, BartTokenizer, LEDTokenizer, AutoTokenizer
from models.customized_modeling_bart import BartForConditionalGeneration
from models.customized_modeling_pegasus import *
from models.customized_modeling_led import *
import gc
import pickle
import warnings

warnings.filterwarnings("ignore")
def main(args):
    
    set_seed(args)
    
    if not os.path.isdir(f"ckpts_{args.result_path}"):
        os.makedirs(f"ckpts_{args.result_path}")

    args.save_model_path = f"ckpts_{args.result_path}" 
    
    if args.test:
        args.load_checkpoint_path = f"ckpts_{args.result_path}"
    

    if th.cuda.is_available() and args.gpu != -1:
        args.device = 'cuda:{}'.format(args.gpu)
    else:
        args.device = 'cpu'

    
    if 't5' in args.model_name:
        tokenizer = T5Tokenizer.from_pretrained(args.model_name)
    elif 'bart' in args.model_name:
        tokenizer = BartTokenizer.from_pretrained('facebook/bart-base')     
    elif 'pegasus' in args.model_name:
        tokenizer = AutoTokenizer.from_pretrained("google/pegasus-x-base")
    elif 'led' in args.model_name:
        tokenizer = LEDTokenizer.from_pretrained("allenai/led-base-16384")

    if args.data == "asap":        
        if "t5" in args.model_name:
            add_tokens = ["@", "{", "}",'<essay>',"<rationale>","[overall]", "[content]", "[organization]", "[word choice]", "[sentence fluency]", "[conventions]","[prompt adherence]", "[language]", "[narrativity]", "[style]","[voice]", 
                            "overall", "content", "organization", "word choice", "sentence fluency", "conventions", "prompt adherence", "language", "narrativity", "style", "voice"]
        else:
            add_tokens = ["@", "{", "}",'<essay>',"<rationale>","[overall]", "[content]", "[organization]", "[word choice]", "[sentence fluency]", "[conventions]","[prompt adherence]", "[language]", "[narrativity]", "[style]","[voice]"]
        
    else:
        add_tokens = ["@", "{", "}",'<essay>',"<rationale>","[cohesion]", "[syntax]", "[vocabulary]", "[phraseology]", "[grammar]", "[conventions]", "1.0", "1.5", 
                      "2.0", "2.5", "3.0", "3.5", "4.0", "4.5", "5.0", "conventions", "grammar", "vocabulary", "phraseology", "syntax", "cohesion"]
        
    tokenizer.add_tokens(add_tokens)

    best_fold_result_dict = dict()
    best_fold_pred_dict = dict()
    best_fold_true_dict = dict()
    sub_best_fold_result_dict = dict()
    sub_best_fold_pred_dict = dict()
    sub_best_fold_true_dict = dict()
    
    for fold in range(5):
        if 't5' in args.model_name:
            model = CustomizedT5ForConditionalGeneration.from_pretrained(args.model_name)
            model.use_rationale = True
            
        elif 'bart' in args.model_name:
            model = BartForConditionalGeneration.from_pretrained('facebook/bart-base')
            model.model.use_rationale = True

        elif 'pegasus' in args.model_name:
            model = PegasusForConditionalGeneration.from_pretrained("google/pegasus-x-base")
            model.model.use_rationale = True
            
        elif 'led' in args.model_name:
            model = LEDForConditionalGeneration.from_pretrained("allenai/led-base-16384")
            model.led.use_rationale = True
            



        
        
        model.resize_token_embeddings(len(tokenizer))

        save_model_fold_path = os.path.join(args.save_model_path, str(fold))
        if not os.path.isdir(save_model_fold_path):
            os.makedirs(save_model_fold_path)
        args.save_model_fold_path = save_model_fold_path
        
        if args.data == "asap":
            TRAIN_DATA_PATH = f"./data/essay/fold_{fold}/train.csv"
            DEV_DATA_PATH = f"./data/essay/fold_{fold}/dev.csv"
            TEST_DATA_PATH = f"./data/essay/fold_{fold}/test.csv"
        else:
            TRAIN_DATA_PATH = f"./data/feedback/fold_{fold}/train.csv"
            DEV_DATA_PATH = f"./data/feedback/fold_{fold}/dev.csv"
            TEST_DATA_PATH = f"./data/feedback/fold_{fold}/test.csv"

        train_data = read_data(TRAIN_DATA_PATH)
        dev_data = read_data(DEV_DATA_PATH)
        test_data = read_data(TEST_DATA_PATH)
        
        train_dataset = train_data.map(lambda x: preprocess_data(x, tokenizer,args), batched=True)
        dev_dataset = dev_data.map(lambda x: preprocess_data(x, tokenizer,args), batched=True)
        test_dataset = test_data.map(lambda x: preprocess_data(x, tokenizer,args), batched=True)
        
        if not args.test:
            print(f"Model Training Fold : {fold}")
            model = train(model, tokenizer, train_dataset, dev_dataset, args)

            for filename in os.listdir(args.save_model_fold_path):
                if filename.startswith("checkpoint-1"):
                    best_model_path = os.path.join(args.save_model_fold_path, filename)
                    best_checkpoint = th.load(best_model_path)
                    model.load_state_dict(best_checkpoint)
                    best_model = model.to(args.device)
        
                    if args.data == "asap":
                        best_result, best_pred_dic, best_true_dic = asap_test(tokenizer, best_model, test_dataset, args)
                    else:
                        best_result, best_pred_dic, best_true_dic = feedback_test(tokenizer, best_model, test_dataset, args)
                    best_model = best_model.cpu()
        
                    del best_model
                    th.cuda.empty_cache()
                    gc.collect()  # Trigger Python garbage collection
        
                elif filename.startswith("checkpoint-2"):
                    sub_best_model_path = os.path.join(args.save_model_fold_path, filename)
                    sub_best_checkpoint = th.load(sub_best_model_path)
                    model.load_state_dict(sub_best_checkpoint)
                    sub_best_model = model.to(args.device)
                    if args.data == "asap":
                        sub_best_result, sub_best_pred_dic, sub_best_true_dic = asap_test(tokenizer, sub_best_model, test_dataset, args)
                    else:
                        sub_best_result, sub_best_pred_dic, sub_best_true_dic = feedback_test(tokenizer, sub_best_model, test_dataset, args)
                    sub_best_model = sub_best_model.cpu()
                    
                    del sub_best_model
                    th.cuda.empty_cache()
                    gc.collect()  # Trigger Python garbage collection

        elif args.test:
            print(f"Model Test Fold : {fold}")
            for filename in os.listdir(args.save_model_fold_path):
                if filename.startswith("checkpoint-1"):
                    best_model_path = os.path.join(args.save_model_fold_path, filename)
                    best_checkpoint = th.load(best_model_path)
                    model.load_state_dict(best_checkpoint)
                    best_model = model.to(args.device)

                    if args.data == "asap":
                        best_result, best_pred_dic, best_true_dic = asap_test(tokenizer, best_model, test_dataset, args)
                    else:
                        best_result, best_pred_dic, best_true_dic = feedback_test(tokenizer, best_model, test_dataset, args)
                    best_model = best_model.cpu()
        
                    del best_model
                    th.cuda.empty_cache()
                    gc.collect()  # Trigger Python garbage collection
        
                elif filename.startswith("checkpoint-2"):
                    sub_best_model_path = os.path.join(args.save_model_fold_path, filename)
                    sub_best_checkpoint = th.load(sub_best_model_path)
                    model.load_state_dict(sub_best_checkpoint)
                    sub_best_model = model.to(args.device)
                    if args.data == "asap":
                        sub_best_result, sub_best_pred_dic, sub_best_true_dic = asap_test(tokenizer, sub_best_model, test_dataset, args)
                    else:
                        sub_best_result, sub_best_pred_dic, sub_best_true_dic = feedback_test(tokenizer, sub_best_model, test_dataset, args)
                    
                    sub_best_model = sub_best_model.cpu()
                    
                    del sub_best_model
                    th.cuda.empty_cache()
                    gc.collect()  # Trigger Python garbage collection

        best_fold_result_dict[fold] = best_result
        best_fold_pred_dict[fold] = best_pred_dic
        best_fold_true_dict[fold] = best_true_dic
        
        
        sub_best_fold_result_dict[fold] = sub_best_result
        sub_best_fold_pred_dict[fold] = sub_best_pred_dic
        sub_best_fold_true_dict[fold] = sub_best_true_dic
        
        with open(f"./{args.result_path}/best_result_dict.pkl", "wb") as f:
            pickle.dump(best_fold_result_dict, f)
        with open(f"./{args.result_path}/best_pred_dict.pkl", "wb") as f:
            pickle.dump(best_fold_pred_dict, f)
        with open(f"./{args.result_path}/best_true_dict.pkl", "wb") as f:
            pickle.dump(best_fold_true_dict, f)
        with open(f"./{args.result_path}/sub_best_result_dict.pkl", "wb") as f:
            pickle.dump(sub_best_fold_result_dict, f)
        with open(f"./{args.result_path}/sub_best_pred_dict.pkl", "wb") as f:
            pickle.dump(sub_best_fold_pred_dict, f)
        with open(f"./{args.result_path}/sub_best_true_dict.pkl", "wb") as f:
            pickle.dump(sub_best_fold_true_dict, f)
        
        
    return best_fold_result_dict, best_fold_pred_dict, best_fold_true_dict, \
        sub_best_fold_result_dict, sub_best_fold_pred_dict, sub_best_fold_true_dict
        



    
    


if __name__ == "__main__":


        parser = argparse.ArgumentParser('Essay Scoring')
        parser.add_argument('--gpu', '-g', type=int, default=0, help='which gpu to use, specify -1 to use CPU')
        parser.add_argument('--train_batch_size', '-trb', type=int, default=4, help='batch_size')
        parser.add_argument('--test_batch_size', '-teb', type=int, default=128, help='test_batch_size')
        parser.add_argument('--seed', '-s', type=int, default=40, help='random seed')
        parser.add_argument('--patience', '-p', type=int, default=10, help='number of patience for early stopping')
        parser.add_argument("--train_epochs", type=int, default=15)
        parser.add_argument("--save_checkpoint_path", type=str, default=None)
        parser.add_argument("--test", type=bool, default=False)
        parser.add_argument("--num_beams", type=int, default=1)
        parser.add_argument("--data", type=str, default=f"asap")
        parser.add_argument("--llm", type=str, default="gpt")
        parser.add_argument('--model_name', '-m', type=str, default='t5-base', help='name of the t5 model')
        parser.add_argument('--learning_rate', '-l', type=float, default=5e-05, help='learning rate')
        
        args = parser.parse_args()

        
        
        

        
        args.result_path = f"{args.data}"
        if not os.path.isdir(args.result_path):
            os.makedirs(args.result_path)
        args.result_path = os.path.join(args.result_path, f"{args.model_name.replace('/', '_')}_{args.llm}")

        
        best_fold_result_dict, best_fold_pred_dict, best_fold_true_dict, \
            sub_best_fold_result_dict, sub_best_fold_pred_dict, sub_best_fold_true_dict = main(args)

        with open(f"./{args.result_path}/final_best_result_dict.pkl", "wb") as f:
            pickle.dump(best_fold_result_dict, f)
        with open(f"./{args.result_path}/final_best_pred_dict.pkl", "wb") as f:
            pickle.dump(best_fold_pred_dict, f)
        with open(f"./{args.result_path}/final_best_true_dict.pkl", "wb") as f:
            pickle.dump(best_fold_true_dict, f)
        with open(f"./{args.result_path}/final_sub_best_result_dict.pkl", "wb") as f:
            
            pickle.dump(sub_best_fold_result_dict, f)
        with open(f"./{args.result_path}/final_sub_best_pred_dict.pkl", "wb") as f:
            pickle.dump(sub_best_fold_pred_dict, f)
        with open(f"./{args.result_path}/final_sub_best_true_dict.pkl", "wb") as f:
            pickle.dump(sub_best_fold_true_dict, f)



