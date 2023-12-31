import numpy as np
import torch
from ..CEF_model.CEF_model import *
import tqdm

def train_delta(model):
    ld = 1
    lr = 0.01
    # Init values
    if_matrix = torch.Tensor(model.dataset.item_feature_matrix)
    uf_matrix = torch.Tensor(model.dataset.user_feature_matrix)
    device = model.device
    # print(f"train device: {device}")
    model = model.to(device)

    # for i, p in enumerate(model.parameters()):
    #     if i > 0:
    #         p.requires_grad = False
    assert model.dataset.feature_num == 500
    for f in tqdm.trange(500): #model.dataset.feature_num
        model.params_i = torch.nn.parameter.Parameter((torch.randn(model.dataset.item_num)/1000).to(device))
        print(model.params_i.device)
        model.params_u = torch.nn.parameter.Parameter((torch.randn(model.dataset.user_num)/1000).to(device))

        optimizer_i = torch.optim.Adam([model.params_i],lr=lr, betas=(0.9,0.999))
        optimizer_u = torch.optim.Adam([model.params_u], lr=lr, betas=(0.9,0.999))

        for i in range(12):
            model.train()
            optimizer_i.zero_grad()
            optimizer_u.zero_grad()

            adjusted_if_matrix = if_matrix.clone().to(device)
            adjusted_uf_matrix = uf_matrix.clone().to(device)
            adjusted_if_matrix[:,f] += model.params_i
            adjusted_uf_matrix[:,f] += model.params_u
                
            model.update_recommendations(adjusted_if_matrix.detach().cpu().numpy(), adjusted_uf_matrix.detach().cpu().numpy())
            disparity = model.get_cf_disparity(model.recommendations, adjusted_if_matrix, adjusted_uf_matrix)
            loss = model.loss_fn(disparity, ld, [model.params_i, model.params_u]).to(device)

            if f == 0:
                print(sum(par.numel() for par in model.parameters() if par.requires_grad))
            
            loss.backward(retain_graph=True)

            # print(f"delta grad size: {model.delta_i.grad.norm()}")

            optimizer_i.step()
            optimizer_u.step()

            model.delta_i[:,f] = model.params_i
            model.delta_u[:,f] = model.params_u

            # if i % 5 == 0:
            #     # print(f"epoch {i}")
            #     # print(f"Disparity: {np.round(disparity[0].detach().cpu().numpy(), 3)}")
            #     # print(f"loss: {np.round(loss[0].detach().cpu().numpy(), 3)}")

            #     # model.evaluate_model()

    return model.delta_i, model.delta_u, model



if __name__ == "__main__":
    model = CEF(featurewise=True)
    delta_i, delta_u, model = train_delta(model)
    torch.save(delta_i, '../../models/CEFout/delta_i_500features_featurewise.pt')
    torch.save(delta_u, '../../models/CEFout/delta_u_500features_featurewise.pt')
    torch.save(model.state_dict(), '../../models/CEF_model_500features_featurewise.model')
