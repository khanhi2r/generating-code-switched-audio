#!/usr/bin/env python3

# Authors: Dorsa Z, Jons Hopkins University (Amir Hussein) 
# Apache 2.0  (http://www.apache.org/licenses/LICENSE-2.0)

import json
import random
from lhotse import *
import torchaudio 
from torchaudio import * 
import torch 
import os.path
import numpy as np
import sys
from datetime import datetime
import math 
random.seed(10)
from lhotse.augmentation.transform import AudioTransform
from dataclasses import dataclass, field
import numpy as np
import torch
from utils import load_pickled
import msgspec

from typing import Callable, Dict, List, Optional, Tuple, Union


@dataclass
class Hamming(AudioTransform):
    """
    Hamming window
    """

    def __call__(self, samples: np.ndarray) -> np.ndarray:
        if isinstance(samples, np.ndarray):
            samples = torch.from_numpy(samples)
        augmented = samples*np.float32(np.hamming(len(samples)))
        return augmented.numpy()

hamming = Hamming()

def add_overlap(sample1, sample2, overlap=int(16000*0.1)):

    sample2 = hamming(sample2)
    new = np.zeros(len(sample1)+len(sample2)-overlap,dtype='float32')
    new[0:len(sample1)] = sample1
    new[len(sample1)-overlap:len(sample1)-overlap+len(sample2)] += sample2
    return new

def load_dicts_modified(sup_dict_path, rec_dict_path):
    supervisions =  msgspec.json.decode(load_pickled(sup_dict_path))
    recordings =  msgspec.json.decode(load_pickled(rec_dict_path))
    return supervisions, recordings


def take_random(token,sups,recordings):
    matched_sups = sups[token]
    sup = random.sample(matched_sups, 1)[0]
    recording = recordings[sup[1]]
    sup = SupervisionSegment(id=sup[0], recording_id=sup[1], start=sup[2], duration=sup[3], channel=0,
                                     text=sup[-1])
    mono_cut = MonoCut(id=sup.id+"-cut", start=sup.start, duration=sup.duration, channel=sup.channel, recording=recording,
                        supervisions=[sup])
    return mono_cut
         
def create_cs_audio(generated_text, output_directory_path, supervisions, recordings): 
    length = len(generated_text)
    transcripts=[]
    for i in range(length):
        line = generated_text[i].split()
        file_name = "uni-"+line[0]

        start_time = datetime.now()
        transcript = file_name + ' '
        sentence_tokens = line[1:]
        a = None #audio 
        index = 0
        energies = 0.0
        
        for j in range(len(sentence_tokens)):
            token = sentence_tokens[j]
            if (token in supervisions):
                transcript += (token+ ' ')
                if index == 0: 
                    c = take_random(token,supervisions,recordings)
                    #c = c.perturb_volume(factor=5.)
                    c_audio =c.load_audio().squeeze()
                    a = c_audio
                    #a = np.pad(c_audio, (0, int(0.05*16000)), 'constant') # padding 0.05s with zeros from both sides
                    a = a/(math.sqrt(audio.audio_energy(a)))
                    a = hamming(a)
                    #print('a energy', audio.audio_energy(a),flush=True)
                    index += 1 
                else:
                    c = take_random(token,supervisions,recordings)
                    #c = c.perturb_volume(factor=5.) #increasing volume because it was too quiet 
                
                    #audio=np.append(audio,np.zeros((int(16000*0.01)),dtype='float32')) #the small pause 
                    #if (len(audio) < int(16000*0.05)): #if segment is too short for overlap of 0.05 secs 
                    #    audio = np.append(audio,np.zeros((int(16000*0.05)-len(audio)),dtype='float32'))
                    audio2 = c.load_audio().squeeze()
                    #audio2 = np.pad(c_audio, (int(0.05*16000), int(0.05*16000)), 'constant')
                    #audio2 = c_audio
                    audio2 = audio2/math.sqrt(audio.audio_energy(audio2)) 
                    #print('audio2 energy', audio.audio_energy(audio2),flush=True)
                    a = add_overlap(a,audio2)
                    #cut=cut.append(audio2)
                    index+=1 

        end_time = datetime.now()
        delta = (end_time - start_time)
        print('making sentence time: ', delta)

        start_time = datetime.now()
        if( index != 0 ):
            transcripts.append(transcript.strip())
            #audio = audio/energies
            torchaudio.save(output_directory_path+'/'+file_name+'.wav', torch.from_numpy(np.expand_dims(a,0)),sample_rate=16000, encoding="PCM_S", bits_per_sample=16)
        end_time = datetime.now()
        delta = (end_time - start_time)

        print('saving audio time: ', delta)

    with open(output_directory_path+'/transcripts.txt','a') as f: #in case there is oov, must use this transcripts as text for training
        for t in transcripts:
            f.write(t+'\n')
 


if __name__ == "__main__":
    sup_dict_path = sys.argv[1]
    rec_dict_path = sys.argv[2]

    input_path = sys.argv[3]
    output_path = sys.argv[4]

    supervisions, recordings= load_dicts_modified(sup_dict_path, rec_dict_path)
        # non_freq_dict_path, sup_bin_1_dict_path, sup_bin_2_dict_path, sup_bin_3_dict_path,
        # sup_bin_4_dict_path, sup_bin_5_dict_path)
    generated_text = open(input_path, 'r').readlines()
    create_cs_audio(generated_text, output_path, supervisions, recordings)
